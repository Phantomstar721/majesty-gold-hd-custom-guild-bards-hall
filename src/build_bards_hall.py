"""Build Custom Guild: Bards Hall from stock resources and approved handoffs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image
from bards_names import features as name_features, name_tables as hero_name_tables
from bards_release import DISPLAY_NAME, SHORT_DESCRIPTION, LONG_DESCRIPTION
from bards_world_effects import append_art as append_world_effects
from bards_dancer_systems import dancer_systems
from bards_abilities import build_descriptions, clone_arcane_note, combat_functions, renown_functions, support_functions, hiring_functions, deflect_functions
from bards_bazaar import bazaar_features
from bards_spell_policy import spell_policy_features
from bards_countermelody import suppression_descriptions, suppression_functions
from bards_panel import THIRD_PRICE_CONTROL
from bards_recruitment_panel import CHILD_DIALOG, manager_features, panel_resources
from bards_chronicles_panel import CONTENT as CHRONICLES
from bards_heroes import describe_hero, hero_data, support_hero_prototype, spellsinger_wander, bard_hunting, dancer_wander
from bards_building_art import append_buildings
from bards_chronicles_art import append_art as append_chronicles_art
from bards_ability_ui import append_art as append_ability_art, features as ability_ui_features
from bards_equipment import append_art as append_equipment_art, features as equipment_features, name_tables as equipment_name_tables
from bards_progression import CAPACITY_BY_LEVEL, CAPACITY_PROPERTY, GUILD_PROTOTYPE, guild_prototype, progression_functions
from cam_io import Entry, Section, append_strings, frame_references, get, name, patch_strings, read, section, u32, write

ROOT = Path(__file__).resolve().parents[1]
MOD_ID = "{e277a34f-bfb6-54ec-bfec-565d735edc37}"
PACKAGE = "CustomGuildBards"
HEROES = (
    ("BDT1", "Troubadour", "Healer"),
    ("BDS1", "Spellsinger", "Cultist"),
    ("BDD1", "Blade_Dancer", "Rogue"),
)
HERO_UI = {"BDT1": "troubadour", "BDS1": "spellsinger", "BDD1": "blade-dancer"}
HERO_UI_SOURCES = {hero_id: ROOT / f"art/hero-interface-v{2 if hero_id == 'BDT1' else 1}/source"
                   for hero_id in HERO_UI}
HERO_UI_SOURCES["BDD1"] = ROOT / "art/blade-dancer-hat-ui-r1"
BUILDINGS = ("BDG1", "BDG2", "BDG3")
PANEL = b"CGBD"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stock_description(root: ET.Element, label: str) -> ET.Element:
    found = root.find(f'.//Description[@Name="{label}"]')
    if found is None:
        raise ValueError(f"Missing stock description {label}")
    return copy.deepcopy(found)


def set_value(root: ET.Element, path: str, value: str) -> None:
    node = root.find(path)
    if node is None:
        parent, field = path.rsplit("/", 1)
        node = ET.SubElement(root.find(parent), field)
    node.set("value", value)


def xml_bytes(root: ET.Element) -> bytes:
    ET.indent(root, space="\t")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_units(sdk: Path) -> bytes:
    buildings = ET.parse(sdk / "Data/M_Buildings.xml").getroot()
    characters = ET.parse(sdk / "Data/M_Characters.xml").getroot()
    result = ET.Element("Majesty")
    healer = stock_description(characters, "Healer")
    for hero_id, title, base in HEROES:
        hero = stock_description(characters, base)
        hero.set("ID", hero_id)
        hero.set("Name", title)
        hero.set("Description", title.replace("_", " "))
        set_value(hero, "./Engine/ImageIDBase", hero_id)
        # Locomotion comes from the stock movement attachment, independently
        # of the Healer-shaped animation frames. Troubadour now matches Ranger;
        # the two combat bards explicitly use Rogue's normal movement.
        movement_source = stock_description(characters, 'Rogue' if title != 'Troubadour' else 'Ranger')
        hero.find('./Engine/Attachment[@kind="Movement"]').set(
            "ID", movement_source.find('./Engine/Attachment[@kind="Movement"]').get("ID"))
        describe_hero(hero, title, hero_id)
        if title == "Troubadour": set_value(hero, "./Engine/DefaultSound", "TroubV")
        if title == "Blade_Dancer": set_value(hero, "./Engine/DefaultSound", "DancV")
        if title == "Spellsinger": set_value(hero, "./Engine/DefaultSound", "SingerV")
        result.append(hero)
    for level, building_id in enumerate(BUILDINGS, 1):
        building = stock_description(buildings, "Warriors_Guild")
        building.set("ID", building_id)
        building.set("Name", f"Bards_Hall{level}")
        building.set("Description", "Bards Hall" if level == 1 else f"Bards Hall Level {level}")
        set_value(building, "./Engine/ImageIDBase", building_id)
        set_value(building, "./Game/DialogID", PANEL.decode())
        set_value(building, "./Game/HelpID", f"hBG{level}")
        set_value(building, "./Game/MaxGuildMembers", str(CAPACITY_BY_LEVEL[level]))
        if level == 1:
            # Private stock MaxHP value; native construction/repair owns HP.
            set_value(building, "./Game/MaxHP", "300")
        produces = building.find("./Game/Produces")
        if len(produces) != len(HEROES):
            raise ValueError("Stock Warriors Guild must have exactly three recruit entries")
        for unit, (_, title, _) in zip(produces, HEROES):
            unit.set("ID", title)
        if level < 3:
            set_value(building, "./Game/UpgradeTo", f"Bards_Hall{level + 1}")
        if level > 1:
            set_value(building, "./Game/UpgradeFrom", f"Bards_Hall{level - 1}")
            # Copy stock Wizard upgrade quote/HP progression, pending balance work.
            upgrade = stock_description(buildings, f"Wizards_Guild{level}")
            # Stock higher guild tiers are reached by UpgradeTo, never offered
            # as separate Palace construction choices. Preserve that flag too.
            flag = upgrade.find('./Game/Flags[@value="NotBuildable"]')
            if flag is None:
                raise ValueError("Stock Wizard upgrade-only flag changed")
            game = building.find('./Game')
            game.insert(list(game).index(game.find('Flags')), copy.deepcopy(flag))
            for field in ("Cost", "MaxHP"):
                set_value(building, "./Game/" + field, upgrade.find("./Game/" + field).get("value"))
        result.append(building)
    return xml_bytes(result)


def extract_function(source: str, function: str) -> str:
    start = re.search(r"(?im)^function\s+" + re.escape(function) + r"\s*\(", source)
    if start is None:
        raise ValueError(f"Missing stock GPL function {function}")
    next_function = re.search(r"(?im)^function\s+\w+\s*\(", source[start.end():])
    end = start.end() + next_function.start() if next_function else len(source)
    block = source[start.start():end]
    return re.sub(r"\s*//[^\n]*\s*$", "", block).rstrip() + "\n"


def data_block(source: str, label: str) -> str:
    match = re.search(r"(?ims)^\[" + re.escape(label) + r"\].*?^\[end\]", source)
    if not match:
        raise ValueError(f"Missing stock GPL data block {label}")
    return match.group() + "\n"


def replace_attribute(block: str, key: str, value: str) -> str:
    result, count = re.subn(r"(?i)(\(" + re.escape(key) + r"\s+)[^)]+(?=\))", lambda m: m[1] + value, block)
    if count != 1:
        raise ValueError(f"Expected one {key} attribute, got {count}")
    return result


def build_gpl(sdk: Path, output: Path) -> list[str]:
    """Privatize stock baseline trees without inheriting unrelated class skills."""
    source = sdk / "GPLMx"
    building_data = (source / "mx_Building_Data.dat").read_text(encoding="cp1252")
    functions = []
    # Hero profiles, decision trees and danger evaluators are package-owned.
    # Common Hero birth/travel/task/level-up mechanisms remain stock calls.
    stock_births = (source / "mx_Building_Births.gpl").read_text(encoding="cp1252")
    birth = extract_function(stock_births, "warriors_guild_birth")
    birth = re.sub(r"(?i)\bwarriors_guild_birth\b", "Bards_Hall_Birth", birth)
    for original, private in (("Warrior_of_discord", "Blade_Dancer"), ("Paladin", "Troubadour"), ("Warrior", "Spellsinger")):
        birth = re.sub(r'(?i)"' + original + r'"', '"' + private + '"', birth)
    functions.append(birth)
    # Stock rehoming and resurrection dispatch through this title lookup.
    # Preserve every stock branch after the new, private hero-name guard.
    guild_title = extract_function((source / "TaskModules/Buildings/Mausoleum.gpl").read_text(encoding="cp1252"), "Guild_Title")
    private_guard = '\n\tif ((ThisAgent\'s "title" == "Troubadour") || (ThisAgent\'s "title" == "Spellsinger") || (ThisAgent\'s "title" == "Blade_Dancer"))\n\t\treturn "Bards_Hall";\n'
    guild_title = re.sub(r"(?im)^begin\s*$", lambda m: m[0] + private_guard, guild_title, count=1)
    functions.append(guild_title)
    guilds = []
    for level in range(1, 4):
        block = data_block(building_data, "Warriors_Guild").replace("[Warriors_Guild]", f"[Bards_Hall{level}]")
        block, replacements = re.subn(r'\{Guild\b', '{' + GUILD_PROTOTYPE, block)
        if replacements != 1:
            raise ValueError('Stock Guild template constructor changed')
        block = replace_attribute(block, "title", "Bards_Hall")
        block = replace_attribute(block, "member_title", "Spellsinger")
        block = replace_attribute(block, "member_basicscript", "Bards_Spellsinger_Tree")
        block = replace_attribute(block, "birthScript2", "Bards_Hall_Birth")
        block = replace_attribute(block, "Lived_In_Script", "Bards_Lived_In")
        if level > 1:
            block = replace_attribute(block, "birthscript", "Bards_Hall_Birth")
        block = block.replace("\n\t}\n", f"\n\t\t(Level {level})\n\t\t({CAPACITY_PROPERTY} {CAPACITY_BY_LEVEL[level]})\n\t\t(Visited_Script Bards_Hall_Visited)\n" + ("\t\t(upgradescript basic_upgrade)\n" if level < 3 else "") + "\t}\n")
        guilds.append(block)
    files = {
        "Bards_Hall_Prototype.gpl": guild_prototype(sdk),
        "Bards_Hero_Data.dat": hero_data(),
        "Bards_Support_Hero_Prototype.gpl": support_hero_prototype(sdk),
        "Bards_Wander_Stock.gpl": spellsinger_wander(sdk, extract_function),
        "Bards_Dancer_Wander_Stock.gpl": dancer_wander(sdk, extract_function),
        "Bards_Hunt_Stock.gpl": bard_hunting(sdk, extract_function),
        "Bards_Building_Data.dat": "\n".join(guilds),
        "Bards_Baseline.gpl": "// Generated private clones of stock Majesty GPL.\n\n" + "\n".join(functions),
        "Bards_Hall_Progression_Stock.gpl": progression_functions(sdk, extract_function),
        "Bards_Arcane_Note.gpl": clone_arcane_note(sdk, extract_function),
        "Bards_Combat.gpl": combat_functions(sdk, extract_function),
        "Bards_Deflect_Stock.gpl": deflect_functions(sdk, extract_function),
        "Bards_Countermelody_Stock.gpl": suppression_functions(sdk, extract_function),
        "Bards_Dancer_Stock.gpl": dancer_systems(sdk, extract_function),
        "Bards_Renown_Stock.gpl": renown_functions(sdk, extract_function),
        "Bards_Support_Stock.gpl": support_functions(sdk, extract_function),
        "Bards_Hiring_Stock.gpl": hiring_functions(sdk, extract_function),
    }
    intents = get(read(sdk.parents[1] / "DataMX/mx_gpltext.cam"), b"STRT", b"AITX")
    intent_count = struct.unpack_from("<H", intents)[0]
    files["Bards_Intent.gpl"] = f'expression #Bards_Intent_Hiring {intent_count}\nexpression #Bards_Intent_Performing {intent_count + 1}\nexpression #Bards_Intent_Prize_Duel {intent_count + 2}\nexpression #Bards_Intent_Hired_Support {intent_count + 3}\n'
    for path in sorted((ROOT / "src/gpl").glob("*.gpl")):
        files[path.name] = path.read_text(encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        (output / filename).write_text(content, encoding="utf-8")
    return list(files)


def load_art_module(game: Path):
    path = ROOT / "src/vendor/troubadour_sprite_package.py"
    spec = importlib.util.spec_from_file_location("bards_troubadour_art", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.REPO = ROOT
    module.RETAIL_CAM = game / "Data/maindata.cam"
    module.HANDOFF = ROOT / "assets/source/approved-troubadour-sprite-set-v1"
    module.PACKAGE_AUTHORITY = ROOT / "reference/healer-package-authority-v2.json"
    return module


def build_main_art(game: Path, output: Path) -> dict:
    art = load_art_module(game)
    handoff = art.load_handoff()
    authority = art.load_package_authority()
    retail, indexed = art.load_retail()
    imag_index, tile_index, palette_index, _ = indexed
    _, healer = art.find_entry(imag_index, art.HEALER_IMAG_NAME)
    private, evidence = art.patch_healer_imag(art.entry_data(retail, healer), authority)
    profile, icon, panel, _, _, _, _ = art.interface_tiles(retail, tile_index)
    tiles = [Entry(e.name, b"") for e in tile_index.entries]
    for record in handoff["records"]:
        payload = (art.HANDOFF / record["tile"]["path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != record["tile"]["sha256"]:
            raise ValueError("Approved sprite payload changed")
        tiles.append(Entry(name(record["cam_name"].encode()), payload))
    tiles.extend((Entry(name(b"TRB1Profile"), profile), Entry(name(b"TRB1HeroIcon"), icon), Entry(name(b"TRB1SelectedPanel"), panel)))
    palettes = [Entry(e.name, art.entry_data(retail, e)) for e in palette_index.entries]
    palettes.append(Entry(name(art.PRIVATE_SPLT_NAME), (art.HANDOFF / handoff["palette"]["path"]).read_bytes()))
    images = []
    hero_ui_evidence = {}
    for hero_id, title, _ in HEROES:
        hero_image = bytearray(private)
        if hero_id in HERO_UI:
            slots = {}
            for set_id, role, size in ((1000, "profile", (100, 100)), (1002, "icon", (25, 25))):
                offset, = frame_references(hero_image, set_id)
                original = u32(hero_image, offset)
                template = tiles[original & 65535].data
                source = HERO_UI_SOURCES[hero_id] / f"{HERO_UI[hero_id]}-{role}.png"
                encoded = interface_tile(art, template, source, size)
                tile_name = f"{hero_id}{role.title()}".encode()
                if len(tiles) > 65535:
                    raise ValueError("Hero UI TILE ordinal exceeds the native low16 reference")
                struct.pack_into("<I", hero_image, offset, (original & 0xFFFF0000) | len(tiles))
                slots[role] = {"tile": tile_name.decode(), "ordinal": len(tiles), "source_sha256": digest(source)}
                tiles.append(Entry(name(tile_name), encoded))
            hero_ui_evidence[hero_id] = slots
        images.append(Entry(name((hero_id + title).encode()), bytes(hero_image)))
    stock = read(game / "Data/maindata.cam")
    warrior = bytearray(get(stock, b"IMAG", b"ABV1Warrior's Guild"))
    stock_tiles = section(stock, b"TILE")
    for set_id, filename, label, size in (
        (1000, "interior-b.png", b"BDG1Interior", (100, 100)),
        (1002, "icon-a.png", b"BDG1ListIcon", (25, 25)),
    ):
        offsets = frame_references(warrior, set_id)
        if len(offsets) != 1:
            raise ValueError("Building interface topology changed")
        offset = offsets[0]
        template = stock_tiles.entries[u32(warrior, offset) & 65535].data
        encoded = interface_tile(art, template, ROOT / "art/ui/bards-guild-options-v1" / filename, size)
        struct.pack_into("<I", warrior, offset, (u32(warrior, offset) & 0xFFFF0000) | len(tiles))
        tiles.append(Entry(name(label), encoded))
    buildings, building_evidence = append_buildings(stock, tiles, palettes, bytes(warrior))
    images.extend(buildings)
    effects, effects_evidence = append_world_effects(stock, tiles, palettes)
    images.extend(effects)
    from bards_world_effects import patch_hero_cast
    images[:3] = [Entry(e.name, patch_hero_cast(e.data, e.name[:4].decode(), authority, tiles)) for e in images[:3]]
    chronicles, chronicles_evidence = append_chronicles_art(stock, tiles, palettes)
    images.append(chronicles)
    from bards_troubadour_refresh import append_art as append_troubadour_art
    troub_evidence = append_troubadour_art(images, tiles, palettes)
    from bards_spellsinger_art import append_art as append_spellsinger_art
    singer_evidence = append_spellsinger_art(images, tiles, palettes)
    from bards_dancer_art import append_art as append_dancer_art
    dancer_evidence = append_dancer_art(images, tiles, palettes)
    write(output, (Section(b"IMAG", bytes(4), tuple(images)), Section(b"TILE", b"\1\0\0\0", tuple(tiles)), Section(b"SPLT", b"\1\0\0\0", tuple(palettes))))
    return {"troubadour_sprite": troub_evidence, "spellsinger_sprite": singer_evidence, "blade_dancer_sprite": dancer_evidence, "world_effects": effects_evidence, "hero_art": evidence, "hero_ui": hero_ui_evidence, "building_art": building_evidence, "chronicles_art": chronicles_evidence, "world_sprite_count": len(handoff["records"]), "selected_ui": {"panel": "A", "interior": "B", "icon": "A"}}


def interface_tile(art, template: bytes, source: Path, size: tuple[int, int]) -> bytes:
    header = art.tile_header(template)
    if header["version"] != 1 or (header["width"], header["height"]) != size or header["row_stride"] != size[0]:
        raise ValueError(f"Native UI tile layout changed for {source.name}: {header}")
    with Image.open(source) as image:
        resized = image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    colours = sorted(set(resized.getdata()))
    if len(colours) < art.VISIBLE_UI_COLOURS:
        # Small icons may already fit losslessly. Pad unused palette entries,
        # never source pixels, to keep the audited embedded TILE layout.
        indices = {rgb: index for index, rgb in enumerate(colours, 1)}
        plane = bytes(indices[rgb] for rgb in resized.getdata())
        present = set(colours)
        candidate = 0
        while len(colours) < art.VISIBLE_UI_COLOURS:
            rgb = (candidate >> 16, (candidate >> 8) & 255, candidate & 255)
            candidate += 1
            if rgb not in present:
                colours.append(rgb)
                present.add(rgb)
        quantized = {"plane": plane, "palette": art.embedded_palette_block(colours)}
    else:
        quantized = art.quantize_interface(resized, source.name)
    prefix = bytearray(template[:26])
    struct.pack_into("<H", prefix, 16, 255)
    struct.pack_into("<H", prefix, 20, 1)
    struct.pack_into("<I", prefix, 22, 26 + size[0] * size[1])
    return bytes(prefix) + quantized["plane"] + quantized["palette"]


def build_panel_art(game: Path, output: Path) -> None:
    stock = read(game / "Data/interfacedata.cam")
    raw = bytearray(get(stock, b"IMAG", b"INTIraw textures"))
    tiles = section(stock, b"TILE")
    references = frame_references(raw, 1034)
    if len(references) != 1 or u32(raw, references[0]) & 65535 != 479:
        raise ValueError("Stock Warriors Guild panel backing changed")
    template = tiles.entries[479].data
    art = load_art_module(game)
    # Native packaging/quantization only; the approved source art remains intact.
    encoded = interface_tile(art, template, ROOT / "art/ui/bards-guild-options-v1/panel-a.png", (200, 245))
    reference = references[0]
    struct.pack_into("<I", raw, reference, (u32(raw, reference) & 0xFFFF0000) | len(tiles.entries))
    new_tiles = [Entry(e.name, b"") for e in tiles.entries] + [Entry(name(b"BDB1PanelBacking"), encoded)]
    equipment_images = append_equipment_art(stock, new_tiles, art, interface_tile)
    ability_images = append_ability_art(game, new_tiles, art, interface_tile)
    palette_sections = tuple(s for s in stock if s.extension == b"SPLT")
    write(output, (Section(b"IMAG", bytes(4), (Entry(name(b"BDTIraw textures"), bytes(raw)), *equipment_images, *ability_images)), Section(b"TILE", tiles.padding, tuple(new_tiles))) + palette_sections)


def private_panel_resources(stock):
    """Private AP52 identities/text before any choice of panel layout."""
    menu = bytearray(get(stock, b"SMNU", b"AP52"))
    # Audited stock image properties: tag 0x0C (IMAG), then 0x0D (set).
    # Fail closed if the source layout changes; never replace arbitrary bytes.
    references = {
        b"INTI": (b"BDTI", (52, 956, 2536, 3296, 3456, 3692, 4524, 4684, 4852)),
        b"AVF1": (b"BDT1", (2968, 4332)),
        b"AVL1": (b"BDS1", (3592,)),
        b"AVM1": (b"BDD1", (2884, 4424)),
    }
    for original, (private, offsets) in references.items():
        found = tuple(offset for offset in range(0, len(menu), 4) if menu[offset:offset + 4] == original)
        if found != offsets:
            raise ValueError(f"Stock AP52 image references changed: {original!r}")
        for offset in offsets:
            if u32(menu, offset - 4) != 12 or u32(menu, offset + 4) != 13:
                raise ValueError("Stock AP52 IMAG property shape changed")
            menu[offset:offset + 4] = private
    strings = patch_strings(get(stock, b"STRT", b"AP52"), {
        0: "Blade Dancer", 1: "Recruit a Blade Dancer", 4: "Troubadour", 5: "Recruit a Troubadour",
        6: "BARDS HALL", 7: "500", 10: "Spellsinger", 11: "Recruit a Spellsinger", 12: "Spellsinger",
        13: "Recruit a Spellsinger", 15: "Destroy this Bards Hall.", 29: "Current number of Blade Dancers",
        31: "Current number of Troubadours", 35: "Current number of Spellsingers",
        39: "Current number of Troubadours", 40: "Current number of Blade Dancers",
        42: "Current number of Blade Dancers", 44: "Current number of Troubadours",
        26: "Current number of Blade Dancers", 27: "Current number of Troubadours",
        32: "500", 33: "Current number of Spellsingers",
    })
    strings = append_strings(strings, {struct.pack('<I', key): value for key, value in {
        47: 'LVL', 48: '1', 49: "This building's current level.",
        50: '2', 51: 'Upgrade the Bards Hall.', 52: '2500',
    }.items()})
    return bytes(menu), strings


def build_text(game: Path, output: Path) -> None:
    stock = read(game / "Data/textdata.cam")
    menu, strings = private_panel_resources(stock)
    menu, child, strings = panel_resources(stock, menu, strings)
    names = {hero_id.encode(): title.replace("_", " ") for hero_id, title, _ in HEROES}
    names.update({bid.encode(): "Bards Hall" for bid in BUILDINGS})
    unit_names = append_strings(get(stock, b"STRT", b"UNTN"), names)
    write(output, (Section(b"SMNU", bytes(4), (Entry(name(PANEL), menu), Entry(name(CHILD_DIALOG), child))),
                   Section(b"STRT", bytes(4), (Entry(name(PANEL), strings), Entry(name(CHILD_DIALOG), strings),
                                              Entry(name(b"UNTN"), unit_names)))))


def build_help(game: Path, output: Path) -> None:
    stock_cam = read(game / "DataMX/mx_gpltext.cam")
    stock = get(stock_cam, b"STRT", b"HPTX")
    from bards_help import help_pages
    pages = help_pages()
    intents = get(stock_cam, b"STRT", b"AITX")
    count = struct.unpack_from("<H", intents)[0]
    private_intents = append_strings(intents, {struct.pack("<I", count): "Hiring a bard", struct.pack("<I", count + 1): "Performing in town", struct.pack("<I", count + 2): "Prize dueling", struct.pack("<I", count + 3): "Supporting as a hired hand"})
    equipment_names = equipment_name_tables(read(game / 'Data/gpltext.cam'))
    write(output, (Section(b"STRT", bytes(4), (Entry(name(b"HPTX"), append_strings(stock, pages)), Entry(name(b"AITX"), private_intents), *equipment_names, *hero_name_tables(read(game / "Data/gpltext.cam")))),))


def manifest(sources: list[str]) -> bytes:
    root = ET.Element("Majesty")
    mod = ET.SubElement(root, "Mod", id=MOD_ID)
    ET.SubElement(mod, "Name").text = PACKAGE
    ET.SubElement(mod, "DisplayName", lang="en_US").text = DISPLAY_NAME
    description = ET.SubElement(mod, "Description", lang="en_US")
    ET.SubElement(description, "Short").text = SHORT_DESCRIPTION
    ET.SubElement(description, "Long").text = LONG_DESCRIPTION
    load = ET.SubElement(ET.SubElement(ET.SubElement(mod, "DataConfiguration"), "Dataset", base="Any"), "Load")
    for filename in ("bards_maindata.cam", "bards_interfacedata.cam", "bards_textdata.cam", "bards_gpltext.cam", "bards_miscdata.cam", "bards_voices.cam", "bards_sounddesc.cam"):
        ET.SubElement(load, "CAM").text = "Data\\" + filename
    ET.SubElement(load, "Descriptions").text = "Data\\bards_units.xml"
    ET.SubElement(load, "Descriptions").text = "Data\\bards_abilities.xml"
    ET.SubElement(load, "Descriptions").text = "Data\\bards_spell_gates.xml"
    ET.SubElement(load, "Descriptions").text = "Data\\bards_sounds.xml"
    gpl = ET.SubElement(load, "GPL")
    ET.SubElement(gpl, "Target").text = "Data\\Bards.bcd"
    for filename in sources:
        ET.SubElement(gpl, "Source").text = "GPL\\" + filename
    return xml_bytes(root)


def build(game: Path, destination: Path) -> dict:
    game, destination = game.resolve(), destination.resolve()
    if not destination.is_relative_to(ROOT / "dist"):
        raise ValueError("Build output must remain in this repository's dist directory")
    if destination.exists():
        raise ValueError("Choose a fresh output directory; existing builds are preserved")
    sdk = game / "SDK/OriginalQuests"
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".bards-staging-", dir=destination.parent))
    data = staging / "Data"
    data.mkdir()
    (data / "bards_units.xml").write_bytes(build_units(sdk))
    (data / "bards_abilities.xml").write_bytes(xml_bytes(build_descriptions(sdk)))
    (data / "bards_spell_gates.xml").write_bytes(xml_bytes(suppression_descriptions(sdk)))
    sources = build_gpl(sdk, staging / "GPL")
    art = build_main_art(game, data / "bards_maindata.cam")
    build_panel_art(game, data / "bards_interfacedata.cam")
    build_text(game, data / "bards_textdata.cam")
    build_help(game, data / "bards_gpltext.cam")
    from bards_audio import build_audio
    build_audio(game, data)
    misc = read(game / "DataMX/mx_miscdata.cam")
    dependencies = get(misc, b"DATA", b"BDEP")
    original_rule = next(line for line in dependencies.splitlines() if line.split() and line.split()[0] == b"ABV1")
    private_rule = original_rule.replace(b"ABV1", b"BDG1", 1)
    write(data / "bards_miscdata.cam", (Section(b"DATA", bytes(4), (Entry(name(b"BDEP"), dependencies + b"\r\n# Bards Hall: stock Warriors Guild prerequisite\r\n" + private_rule + b"\r\n"),)),))
    compiler_dir = ROOT / "artifacts/compiler"
    compiler_dir.mkdir(parents=True, exist_ok=True)
    project = compiler_dir / "Bards.gplproj"
    project.write_text("".join(f'{"data" if p.endswith(".dat") else "source"}="{(staging / "GPL" / p).as_posix()}"\n' for p in sources), encoding="utf-8")
    compile_result = subprocess.run([str(game / "SDK/Gplbcc.exe"), "-in", str(project), "-out", str(data / "Bards.bcd"), "-stdout"], cwd=compiler_dir, capture_output=True, text=True)
    (compiler_dir / "compile.log").write_text(compile_result.stdout + compile_result.stderr, encoding="utf-8")
    if compile_result.returncode or not (data / "Bards.bcd").is_file():
        raise RuntimeError(f"GPL compilation failed; see {compiler_dir / 'compile.log'}")
    (staging / f"{PACKAGE}.mmxml").write_bytes(manifest(sources))
    definition = {"schema_version": 3, "mod_id": MOD_ID, "internal_name": PACKAGE, "display_name": DISPLAY_NAME, "custom_buildings": [{"local_name": "Bards_Hall", "controller_base": "AP52", "panel_resource_template": "AP52"}], "runtime_features": [{"type": "stock.native-timing.v1", "spell_ids": ["BVA1", "BMA1", "BSA1", "BRA1"], "effector_ids": ["BYV1", "BME2", "BME1", "BSE1", "BRE1", "BNE1", "BCE1"]}]}
    definition['runtime_features'].append({
        'type': 'manager.overlay-movement-scale.v1', 'overlay_id': 'BME2', 'percent': 115,
    })
    definition['runtime_features'].extend(manager_features())
    definition['runtime_features'].extend(spell_policy_features())
    definition['runtime_features'].extend(ability_ui_features())
    definition['runtime_features'].extend(equipment_features())
    definition['runtime_features'].extend(name_features())
    definition['runtime_features'].extend(bazaar_features())
    definition['runtime_features'].append({
        'type': 'stock.gameplay-event-observer.v1', 'feature_key': 'bards-renown-bounty',
        'event': 'attack-flag-completed', 'callback_symbol': 'Bards_Renown_Completed_Bounty',
    })
    definition['runtime_features'].append({
        'type': 'stock.activity-duration.v1', 'feature_key': 'bards-hiring',
        'api_prefix': 'Bards_Contract', 'condition_callback_symbol': 'Bards_Hire_Condition',
        'completion_callback_symbol': 'Bards_Hire_Completed',
        'cancellation_callback_symbol': 'Bards_Hire_Cancelled',
    })
    for key, prefix, callback in (('bards-street-show', 'Bards_Show', 'Bards_Street_Show'),
                                   ('bards-street-audience', 'Bards_Audience', 'Bards_Street_Audience')):
        definition['runtime_features'].append({
            'type': 'stock.activity-duration.v1', 'feature_key': key, 'api_prefix': prefix,
            'condition_callback_symbol': callback + '_Condition',
            'completion_callback_symbol': callback + '_Completed',
            'cancellation_callback_symbol': callback + '_Cancelled',
        })
    (staging / "mod-definition.json").write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")
    from validate_bards_hall import check
    check(game, staging)
    report = {
        "status": "release-candidate", "output": str(destination),
        "release_ready": False, "installed": False, "display_name": DISPLAY_NAME,
        "wired": ["level-1 Arcane Note and level-8 Resonant Burst", "Prize Duel, Rousing Finale and Encore and private intent",
                  "persistent stock-derived support with all four staged Troubadour songs",
                  "native completion cooldowns, expiry queries and nonstacking self/allied snapshots",
                  "fixed native-period-derived March/Satire deltas and bounded useful-song waiting",
                  "Renown source attribution, stock death/bounty boundaries and guild settlement",
                  "paid existing-bard hiring, class preferences and saved shared-service contracts",
                  "level-3 shared Resonance and echo; level-5 Countermelody; level-8 Burst consumes Resonance for Crescendo",
                  "level-3 parry-only Riposte and level-8 same-enemy Dueling Flourish",
                  "level-5 shared eight-second Deflect before Dodge/MR, including audited direct spell payloads",
                  "level-5 Countermelody: resisted eight-second accuracy debuff and selective spell suppression",
                  "Street Spectacle: outdoor action, shared timed audience dwell, affordable tips and bounded XP",
                  "200-gold hiring split: 100 guild / 100 hired bard, with 50-gold patron reserve",
                  "main guild panel with standard utilities/counts and separate full-width recruitment subpanel",
                  "Manager stock.ap52-recruitment-panel.v1 navigation and native shared queue",
                  "three private stock.hero-quest-participant.v1 trees with provider-optional quest participation",
                  "stock.spell-evaluation-equivalent.v1 Arcane Note/Burst combat confidence",
                  "explicit private hero profiles, private decision trees and source-class-free danger evaluators",
                  "three stock.equipment.v1 weapon identities with twelve native tier icons and private rank names; stock armor assignments",
                  "primary Arcane Note weapon upgrade bonuses and stock weapon shopping preference",
                  "Epic Chronicles compact primary row and manager.kingdom-research.v1 declaration: level 3, 3000 gold, 15% earned gold/XP",
                  "approved nearby support XP at half combat/exploration base; reduced once-per-song XP",
                  "self-useful March during follow travel and two-step Spellsinger fallback",
                  "BME2 overlay movement scale at 115 percent; saved BME1 expires before new March applies",
                  "AP78 spell/passive/enchantment rows, tooltips and approved stock-referenced native icons",
                  "Golden Chorus custom pixels in the stock Super Charge playback framework",
                  "approved private voice banks for all three bards, including revised Troubadour Level 10 and Death",
                  "base/expansion death-field guards and shared Flourish damage/oil routing",
                  "central spell-policy discovery and persistent caster attribution for Refrain"],
        "prepared": [],
        "pending": ["recorded sprite and spell-effect presentation checks in the recombined game",
                    "native acceptance of adversarial-review repairs in base and expansion quests"],
        "art": art,
        "files": {str(p.relative_to(staging)): digest(p) for p in sorted(staging.rglob("*")) if p.is_file()},
    }
    (ROOT / "artifacts/build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    staging.rename(destination)
    project.write_text("".join(f'{"data" if p.endswith(".dat") else "source"}="{(destination / "GPL" / p).as_posix()}"\n' for p in sources), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-path", type=Path, default=Path(r"C:\Program Files (x86)\Steam\steamapps\common\Majesty HD"))
    parser.add_argument("--output", type=Path, default=ROOT / "dist/CustomGuildBards")
    args = parser.parse_args()
    build(args.game_path, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
