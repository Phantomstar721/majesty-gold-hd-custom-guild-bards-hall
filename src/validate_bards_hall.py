"""Validate the development foundation against stock and approved art sources.

This is a static package audit, not a simulation of Majesty's native runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET

from build_bards_hall import BUILDINGS, HEROES, HERO_UI, MOD_ID, ROOT, data_block, extract_function, load_art_module
from bards_progression import CAPACITY_BY_LEVEL, validate_progression, validate_compiled_capacity
from bards_panel import THIRD_PRICE_CONTROL, control_index, records
from bards_recruitment_panel import CHILD_DIALOG, OPEN_RECRUIT, manager_features
from bards_chronicles_panel import ACTION, PROGRESS, ACTIVE, PRICE, ICON, CONTENT, manager_feature
from bards_building_art import descriptors, validate_buildings
from cam_io import frame_references, get, read, section, u32


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strings(blob):
    count = struct.unpack_from("<H", blob)[0]
    return {blob[offset:offset + 4]: blob[offset + 4:blob.index(b"\0", offset + 4)]
            for offset in struct.unpack_from(f"<{count}I", blob, 4)}


def check(game: Path, package: Path) -> None:
    from bards_world_effects import validate as validate_world_effects, SPECS, streams
    validate_world_effects(game, package)
    art = load_art_module(game)
    # The imported sprite authority independently fingerprints retail inputs.
    retail, indexed = art.load_retail()
    authority = art.load_package_authority()
    handoff = json.loads((art.HANDOFF / "manifest.json").read_text())
    source = read(game / "Data/maindata.cam")
    output = read(package / "Data/bards_maindata.cam")
    images = section(output, b"IMAG")
    require(len(images.entries) == 8 + len(SPECS), "Expected heroes, guilds, Chronicles, Crescendo and all approved spell effects")
    _, healer_entry = art.find_entry(indexed[0], art.HEALER_IMAG_NAME)
    expected_hero, _ = art.patch_healer_imag(art.entry_data(retail, healer_entry), authority)
    stock_tiles, new_tiles = section(source, b"TILE"), section(output, b"TILE")
    for hero_id, title, _ in HEROES:
        actual = bytearray(get(output, b"IMAG", (hero_id + title).encode()))
        if hero_id in HERO_UI:
            for set_id, role, size in ((1000, "profile", (100, 100)), (1002, "icon", (25, 25))):
                offset, = frame_references(actual, set_id)
                original_offset, = frame_references(expected_hero, set_id)
                actual_word, original_word = u32(actual, offset), u32(expected_hero, original_offset)
                require(actual_word >> 16 == original_word >> 16, "Hero UI reference flags changed")
                tile = new_tiles.entries[actual_word & 65535]
                require(tile.name.rstrip(b"\0") == f"{hero_id}{role.title()}".encode(),
                        f"{title}: wrong {role} identity")
                require(art.decode_tile_v1(tile.data).size == size, f"{title}: wrong native {role} size")
                struct.pack_into("<I", actual, offset, original_word)
        from bards_world_effects import patch_hero_cast
        expected_cast = patch_hero_cast(expected_hero, hero_id, authority, new_tiles.entries)
        if hero_id == "BDT1":
            from bards_troubadour_refresh import adapter as troub_adapter, HANDOFF as TROUB_HANDOFF
            palettes = section(output, b"SPLT").entries
            start = len(new_tiles.entries)-1017-681-809
            expected_cast, troub_tiles, troub_palettes, _ = troub_adapter().integrate(
                expected_cast, TROUB_HANDOFF, tile_start=start,
                hero_palette_index=len(palettes)-6, dead_palette_index=len(palettes)-5)
            require([(e.name.rstrip(b"\0").decode(),e.data) for e in new_tiles.entries[start:start+809]] == troub_tiles,
                    "Troubadour TILE payload/relocation differs from approved handoff")
            require([(e.name.rstrip(b"\0").decode(),e.data) for e in palettes[-6:-4]] == troub_palettes,
                    "Troubadour palettes differ from approved handoff")
        if hero_id == "BDS1":
            from bards_spellsinger_art import adapter as singer_adapter, HANDOFF as SINGER_HANDOFF, TILE_COUNT
            palettes = section(output, b"SPLT").entries
            expected_cast, singer_tiles, singer_palettes, _ = singer_adapter().integrate(
                expected_cast, SINGER_HANDOFF, tile_start=len(new_tiles.entries)-1017-TILE_COUNT,
                hero_palette_index=len(palettes)-4, dead_palette_index=len(palettes)-3)
            require([(e.name.rstrip(b"\0").decode(),e.data) for e in new_tiles.entries[-1017-TILE_COUNT:-1017]] == singer_tiles,
                    "Spellsinger TILE payload/relocation differs from approved handoff")
            require([(e.name.rstrip(b"\0").decode(),e.data) for e in palettes[-4:-2]] == singer_palettes,
                    "Spellsinger palettes differ from approved handoff")
        if hero_id == "BDD1":
            from bards_dancer_art import adapter, HANDOFF
            palettes = section(output, b"SPLT").entries
            expected_cast, dancer_tiles, dancer_palettes, _ = adapter().integrate(
                expected_cast, HANDOFF, tile_start=len(new_tiles.entries)-1017,
                hero_palette_index=len(palettes)-2, dead_palette_index=len(palettes)-1)
            require([(e.name.rstrip(b"\0").decode(), e.data) for e in new_tiles.entries[-1017:]] == dancer_tiles,
                    "Blade Dancer TILE payload/relocation differs from approved handoff")
            require([(e.name.rstrip(b"\0").decode(), e.data) for e in palettes[-2:]] == dancer_palettes,
                    "Blade Dancer palettes differ from approved handoff")
        require(bytes(actual) == expected_cast,
                f"{title}: approved sprite topology or preserved UI/cast stream differs")
    require([(e.name, e.data) for e in new_tiles.entries[:len(stock_tiles.entries)]] ==
            [(e.name, b"") for e in stock_tiles.entries], "Stock TILE positions were altered")
    require(section(output, b"SPLT").entries[:len(section(source, b"SPLT").entries)] == section(source, b"SPLT").entries,
            "Stock palettes were altered")
    private_tiles = new_tiles.entries[len(stock_tiles.entries):]
    effect_count = sum(len(refs) for _, _, prefix, _ in SPECS for _, _, _, refs in streams(next(e.data for e in section(source,b"IMAG").entries if e.name.startswith(prefix.encode()))))
    crescendo_count = sum(len(refs) for _, _, _, refs in streams(next(e.data for e in section(source,b"IMAG").entries if e.name.startswith(b'HRB2'))))
    require(len(private_tiles) == len(handoff["records"]) + 5 + 2 * len(HERO_UI) + 61 + 60 + effect_count + crescendo_count + 1017 + 681 + 809 + 1, "Unexpected private TILE count")
    for tile, record in zip(private_tiles, handoff["records"]):
        require(hashlib.sha256(tile.data).hexdigest() == record["tile"]["sha256"],
                "Approved world sprite payload changed")
    warrior = get(source, b"IMAG", b"ABV1Warrior's Guild")
    validate_buildings(source, output)
    from bards_chronicles_art import validate_art
    validate_art(source, output)

    for bid in BUILDINGS:
        private = get(output, b"IMAG", (bid + "Bards Hall").encode())
        for set_id, size in ((1000, (100, 100)), (1002, (25, 25))):
            offset, = frame_references(private, set_id)
            stock_set, private_set = descriptors(warrior)[set_id], descriptors(private)[set_id]
            # Both UI descriptors end with their single native TILE reference.
            require(private_set[:-4] == stock_set[:-4] and private_set[-2:] == stock_set[-2:],
                    'Building UI descriptor changed outside the private TILE index')
            payload = new_tiles.entries[u32(private, offset) & 65535].data
            require(art.decode_tile_v1(payload).size == size, "Building UI size changed")
    panel = read(package / "Data/bards_interfacedata.cam")
    interface = read(game / "Data/interfacedata.cam")
    panel_imag = get(panel, b"IMAG", b"BDTIraw textures")
    original_imag = get(interface, b"IMAG", b"INTIraw textures")
    offset, = frame_references(original_imag, 1034)
    require(len(panel_imag) == len(original_imag) and all(
        left == right or pos in (offset, offset + 1) for pos, (left, right) in enumerate(zip(original_imag, panel_imag))),
        "Private backing changed other stock interface references")
    require(art.decode_tile_v1(section(panel, b"TILE").entries[u32(panel_imag, offset) & 65535].data).size == (200, 245),
            "Panel is not native size")
    units = ET.parse(package / "Data/bards_units.xml").getroot()
    require(len(units) == 6, "Unexpected unit description count")
    for hero_id, title, _ in HEROES:
        hero = units.find(f'./Description[@ID="{hero_id}"]')
        require(hero is not None and hero.get("Name") == title, "Private hero identity changed")
        require(hero.find("./Game/Cost").get("value") == "500", "Recruit prices must be equal at 500")
    for level, bid in enumerate(BUILDINGS, 1):
        building = units.find(f'./Description[@ID="{bid}"]')
        require(building.find("./Game/MaxGuildMembers").get("value") == str(CAPACITY_BY_LEVEL[level]),
                "Shared guild capacity must be 4/6/8 by tier")
        require([p.get("ID") for p in building.find("./Game/Produces")] == [h[1] for h in HEROES],
                "Recruit indices differ from the native command contract")
        require(building.find("./Game/DialogID").get("value") == "CGBD", "Unexpected guild dialog")
        if level == 1:
            require(building.find("./Game/MaxHP").get("value") == "300", "Level-one Bards Hall must start at 300 HP")
        require((building.find('./Game/Flags[@value="NotBuildable"]') is not None) == (level > 1),
                "Only the first guild tier may appear in the Palace construction list")
        if level < 3:
            require(building.find("./Game/UpgradeTo").get("value") == f"Bards_Hall{level + 1}", "Broken upgrade chain")
        if level > 1:
            require(building.find("./Game/UpgradeFrom").get("value") == f"Bards_Hall{level - 1}", "Broken previous tier")
    text = read(package / "Data/bards_textdata.cam")
    names = strings(get(text, b"STRT", b"UNTN"))
    stock_names = strings(get(read(game / "Data/textdata.cam"), b"STRT", b"UNTN"))
    require(all(names[key] == value for key, value in stock_names.items()), "Stock unit names changed")
    help_pages = strings(get(read(package / "Data/bards_gpltext.cam"), b"STRT", b"HPTX"))
    stock_help = strings(get(read(game / "DataMX/mx_gpltext.cam"), b"STRT", b"HPTX"))
    require(all(help_pages[key] == value for key, value in stock_help.items()), "Stock help text changed")
    for unit in units:
        require(unit.get("ID").encode() in names, "Private unit name is missing")
        require(unit.find("./Game/HelpID").get("value").encode() in help_pages, "Private help page is missing")
    menu = get(text, b"SMNU", b"CGBD")
    require(all(key in menu for key in (b"BDTI", b"BDT1", b"BDS1", b"BDD1")), "Panel uses the wrong art identities")
    controls = records(menu)
    for control in (OPEN_RECRUIT, 0x1F44, 0x1F5D, 0x1F42, 0x1F58, 0x1F59,
                    0x1F1B, 0x1F0D, 0x1F1C, 0x1F19, 0x1F52, 0x1F1A,
                    0x1F47, 0x1F4F, 0x1E28, ACTION, PROGRESS, ACTIVE, PRICE):
        record = controls[control_index(controls, control)]
        x, y, width, height = struct.unpack_from('<4I', record, 8)
        require(x + width <= 200 and y + height <= 245, f'Private panel control {control:#x} is clipped')
    for control in (0x22CE, 0x1F49, 0x1181, 0x1F11, 0x1F12, 0x1F13, 0x1F14,
                    0x1F48, 0x1389, 0x1388, 0x1752, 0x1F51, THIRD_PRICE_CONTROL,
                    0x1F56, 0x1F57):
        record = controls[control_index(controls, control)]
        require(struct.unpack_from('<2I', record, 8) == (1500, 1500), 'Legacy AP52 alternate layout must remain offscreen')
    child = records(get(text, b'SMNU', CHILD_DIALOG))
    for control in (0x1F48, 0x1389, 0x1388, 0x1752, 0x1F51, THIRD_PRICE_CONTROL,
                    0x1F56, 0x1F57, 0x1F4D):
        x, y, width, height = struct.unpack_from('<4I', child[control_index(child, control)], 8)
        require(x + width <= 202 and y + height <= 245, f'Recruitment child control {control:#x} is clipped')
    definition = json.loads((package / 'mod-definition.json').read_text())
    require([f for f in definition['runtime_features'] if f['type'] == 'manager.overlay-movement-scale.v1'] ==
            [{'type': 'manager.overlay-movement-scale.v1', 'overlay_id': 'BME2', 'percent': 115}],
            'March requires the approved native 15-percent movement scale on its new overlay only')
    require([f for f in definition['runtime_features'] if f['type'] == 'manager.kingdom-research.v1']
            == [manager_feature()], 'Epic Chronicles must declare its exact approved Manager contract once')
    for control in (ACTION, PROGRESS, ACTIVE, PRICE, ICON):
        control_index(controls, control)
        require(not any(struct.pack('<II', 6, control) in record for record in child),
                'Epic Chronicles belongs only on the primary panel')
    labels = strings(get(text, b'STRT', b'CGBD'))
    require(labels[struct.pack('<I', 58)] == CONTENT['research_description'].encode('cp1252'),
            'Epic Chronicles tooltip differs from its approved activation and ownership rules')
    from bards_help import help_pages as authored_help_pages
    require(all(help_pages[key] == value.encode('cp1252')
                for key, value in authored_help_pages().items()),
            'Bard and guild help must match the current individual descriptions')
    require(all(term in help_pages[b'hBG3'] for term in
                (b'3000', b'15%', b'completed level-3', b'need not be purchased again')),
            'Level-3 help must explain Chronicles cost, benefit and restoration')
    require(all(feature in definition['runtime_features'] for feature in manager_features()),
            'Package is missing a research, recruitment-child or private-hero integration declaration')
    require(not any(f['type'] == 'stock.ap52-private-recruitment.v1' for f in definition['runtime_features']),
            'Obsolete inline recruitment recipe must not remain enabled')
    from bards_equipment import validate as validate_equipment
    validate_equipment(game, package, art)
    from bards_ability_ui import validate as validate_ability_ui, features as ability_ui_features
    from build_bards_hall import interface_tile
    validate_ability_ui(game, package, art, interface_tile)
    require([f for f in definition['runtime_features'] if f['type'] == 'stock.ap78-info-row.v1'] == ability_ui_features(),
            'AP78 skill/effect presentation differs from authored content')
    baseline = (package / "GPL/Bards_Baseline.gpl").read_text()
    stock_lookup = extract_function((game / "SDK/OriginalQuests/GPLMx/TaskModules/Buildings/Mausoleum.gpl").read_text(encoding="cp1252"), "Guild_Title")
    private_lookup = extract_function(baseline, "Guild_Title")
    private_lookup = re.sub(r'\n\s*if \(\(ThisAgent\x27s "title" == "Troubadour"\).*?return "Bards_Hall";\n', '', private_lookup, count=1, flags=re.S)
    require(private_lookup.split() == stock_lookup.split(), "Stock Guild_Title branches changed")
    from validate_bards_abilities import check_abilities
    check_abilities(game / 'SDK/OriginalQuests', package, extract_function)
    from validate_bards_abilities import stock_equal
    validate_progression(game / 'SDK/OriginalQuests', package, extract_function,
                         data_block, stock_equal, require)
    validate_compiled_capacity(package, data_block, require)
    from validate_bards_heroes import check_heroes
    check_heroes(game / 'SDK/OriginalQuests', package, extract_function, stock_equal, require)
    # Independently re-serialize every generated archive with the audited writer.
    with tempfile.TemporaryDirectory() as temporary:
        reference = Path(temporary) / "reference.cam"
        for path in (package / "Data").glob("*.cam"):
            art.write_cam(reference, read(path))
            require(reference.read_bytes() == path.read_bytes(), f"Invalid native CAM encoding: {path.name}")
    # Read-only Manager contract and resource inventory; never compose a profile.
    sys.path.insert(0, str(ROOT.parent / "majesty-gold-hd-cam-merger/src"))
    from majesty_cam.package import load_package
    from majesty_cam.compose import (SelectedMod, inventory_package, resolve_runtime_feature_registry,
                                     resolve_controller_registry, validate_controller_stock_evidence)
    inventory = inventory_package(SelectedMod("bards", load_package(package)))
    from majesty_cam.shared_features import StockGameplayEventObserver
    require(any(isinstance(feature, StockGameplayEventObserver)
                and feature.event == 'attack-flag-completed'
                and feature.callback_symbol == 'Bards_Renown_Completed_Bounty'
                for feature in inventory.selected.package.definition.runtime_features),
            'Renown requires the shared stock attack-flag completion observer')
    # Pure declaration/resource proof, with no profile build or package output.
    runtime_features = resolve_runtime_feature_registry((inventory,))
    controller = resolve_controller_registry((inventory,))
    require(len(controller.registry.private_recruitments) == 1,
            'Expected one declared private recruitment controller')
    require(controller.registry.private_recruitments[0].third_price_control_id == THIRD_PRICE_CONTROL,
            'Native third price binding differs from the authored panel')
    validate_controller_stock_evidence(
        game, (inventory,), controller.registry,
        controller_panels=controller.panels,
        controller_toggles=controller.toggles,
        runtime_feature_registry=runtime_features,
    )
    # Use the catalog's full read-only check, not discovery alone: this includes
    # unsafe GPL control flow, private text bindings and native feature evidence.
    from majesty_cam.manager.compatibility import CompatibilityRegistry
    from majesty_cam.manager.preflight import catalog_merge_preflight
    issues = catalog_merge_preflight(
        MOD_ID, "Custom Guild: Bards Hall", package,
        registry=CompatibilityRegistry({}), game_path=game,
    )
    require(not issues, "Manager merge readiness rejected the package:\n" + "\n".join(
        f"{issue.code}: {issue.path}: {issue.message}" for issue in issues))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-path", type=Path, default=Path(r"C:\Program Files (x86)\Steam\steamapps\common\Majesty HD"))
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    check(args.game_path, args.package)
