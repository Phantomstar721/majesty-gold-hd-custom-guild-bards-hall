"""Stage the owned Bards Hall source package for upload, without publishing."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MOD_ID = '{e277a34f-bfb6-54ec-bfec-565d735edc37}'
TITLE = 'Custom Guild: Bards Hall'
MARKER = '.custom-guild-bards-workshop-stage'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    root = root.resolve(strict=True)
    found = {}
    for p in [root] + list(root.rglob('*')):
        if p.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Linked staging input: ' + str(p))
        if not p.resolve(strict=True).is_relative_to(root):
            raise ValueError('Path escapes staging root: ' + str(p))
        if p.is_file():
            found[str(p.relative_to(root))] = digest(p)
    return found


def runtime_files(package):
    manifest = package / 'CustomGuildBards.mmxml'
    tree = ET.parse(manifest).getroot()
    mod = tree.find('Mod')
    if mod.get('id').lower() != MOD_ID or mod.find('DisplayName').text != TITLE:
        raise ValueError('Incorrect package identity')
    files = {'CustomGuildBards.mmxml', 'mod-definition.json'}
    for node in mod.findall('./DataConfiguration/Dataset/Load//*'):
        if node.tag not in {'CAM', 'Descriptions', 'Target', 'Source'}:
            continue
        relative = PurePosixPath(node.text.strip().replace('\\', '/'))
        if relative.is_absolute() or '..' in relative.parts or ':' in str(relative):
            raise ValueError('Unsafe manifest path: ' + str(relative))
        files.add(relative.as_posix())
    definition = json.loads((package / 'mod-definition.json').read_text(encoding='utf-8'))
    if (definition['mod_id'].lower() != MOD_ID or definition['schema_version'] != 3
            or definition['display_name'] != TITLE or not definition['runtime_features']):
        raise ValueError('Incomplete Manager contract')
    if not any(p.startswith('GPL/') for p in files):
        raise ValueError('Manager composition requires the referenced GPL sources')
    return sorted(files)


def workshop_text(text):
    text = re.sub(r'^### (.+)$', r'[h3]\1[/h3]', text, flags=re.M)
    text = re.sub(r'^## (.+)$', r'[h2]\1[/h2]', text, flags=re.M)
    text = re.sub(r'^# (.+)$', r'[h1]\1[/h1]', text, flags=re.M)
    text = re.sub(r'\*\*(.+?)\*\*', r'[b]\1[/b]', text, flags=re.S)
    text = re.sub(r'\[([^\]\n]+)\]\((https?://[^)]+)\)', r'[url=\2]\1[/url]', text)
    # Keep every indented continuation inside its corresponding list item.
    output, in_list = [], False
    for line in text.splitlines():
        if line.startswith('- '):
            if not in_list:
                output.append('[list]')
                in_list = True
            output.append('[*]' + line[2:])
        elif in_list and line.startswith('  '):
            output.append(line.strip())
        else:
            if in_list:
                output.append('[/list]')
                in_list = False
            output.append(line)
    if in_list:
        output.append('[/list]')
    return '\n'.join(output).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workshop-id', default=None)
    args = parser.parse_args()
    report = json.loads((ROOT / 'artifacts/build-report.json').read_text())
    package = Path(report['output']).resolve(strict=True)
    dist = (ROOT / 'dist').resolve(strict=True)
    if not package.is_relative_to(dist):
        raise ValueError('Build input must be inside this repository dist directory')
    if inventory(package) != report['files']:
        raise ValueError('Build input changed after validation')
    files = runtime_files(package)
    project_path = ROOT / 'workshop/CustomGuildBards.mswproj'
    workshop_id, visibility = '0', 'Private'
    if project_path.exists():
        prior = ET.parse(project_path).getroot().find('SteamWorkshop')
        workshop_id, visibility = prior.get('id'), prior.get('visibility')
    if args.workshop_id is not None:
        workshop_id = args.workshop_id
    if not re.fullmatch(r'0|[1-9][0-9]*', workshop_id):
        raise ValueError('Invalid Workshop ID')
    if visibility not in {'Private', 'Public', 'FriendsOnly'}:
        raise ValueError('Invalid Workshop visibility')
    preview = ROOT / 'assets/workshop/workshop-preview.jpg'
    instructions = ROOT / 'release/START HERE.txt'
    for p in (preview, instructions):
        if not p.is_file():
            raise ValueError('Missing upload input: ' + str(p))
    if preview.stat().st_size >= 1024 * 1024:
        raise ValueError('Preview must remain below 1 MiB')
    description = workshop_text((ROOT / 'WORKSHOP.md').read_text(encoding='utf-8'))
    target = dist / 'workshop-upload'
    if target.exists():
        inventory(target)
        if not (target / MARKER).is_file():
            raise ValueError('Upload stage is not owned by this repository')
    stage = Path(tempfile.mkdtemp(prefix='.bards-workshop-', dir=str(dist)))
    content = stage / 'content'
    content.mkdir()
    for relative in files:
        source = package / relative
        if not source.is_file() or not source.resolve(strict=True).is_relative_to(package):
            raise ValueError('Missing/unsafe runtime file: ' + relative)
        destination = content / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(instructions, content / 'START HERE.txt')
    content_hashes = inventory(content)
    if set(content_hashes) != {str(Path(p)) for p in files} | {'START HERE.txt'}:
        raise ValueError('Unexpected upload content')
    for relative in files:
        key = str(Path(relative))
        if content_hashes[key] != report['files'][key]:
            raise ValueError('Upload bytes differ from validated build: ' + relative)
    (stage / MARKER).write_text('schema=1\n', encoding='ascii')
    (stage / 'SHA256.txt').write_text(''.join(
        f'{value}  {Path(key).as_posix()}\n' for key, value in sorted(content_hashes.items())), encoding='ascii')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    receipt = dict(schema='bards-hall-workshop-stage/v1', staged_at_utc=datetime.now(timezone.utc).isoformat(),
                   source=str(package), commit=revision, title=TITLE, workshop_id=workshop_id,
                   content=str(target / 'content'), project=str(project_path), preview=str(preview),
                   files=content_hashes, preview_sha256=digest(preview), uploaded=False)
    (stage / 'stage-report.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    # Preserve the prior owned stage rather than deleting any filesystem tree.
    if target.exists():
        backup = dist / ('.bards-workshop-backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        if not target.resolve(strict=True).is_relative_to(dist) or not backup.resolve().is_relative_to(dist):
            raise ValueError('Stage replacement escapes dist')
        target.rename(backup)
    stage.rename(target)
    project = ET.Element('Majesty')
    workshop = ET.SubElement(project, 'SteamWorkshop', id=workshop_id, visibility=visibility)
    ET.SubElement(workshop, 'Title', lang='en_US').text = TITLE
    ET.SubElement(workshop, 'Description', lang='en_US').text = description
    ET.SubElement(workshop, 'ContentPath').text = str(target / 'content')
    ET.SubElement(workshop, 'PreviewImagePath').text = str(preview)
    for tag in ('Mod', 'Character', 'Building', 'Weapon', 'Spell', 'Audio', 'Original Rules', 'Northern Expansion Rules'):
        ET.SubElement(workshop, 'IDTag').text = tag
    ET.indent(project, space='\t')
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_bytes(ET.tostring(project, encoding='utf-8', xml_declaration=True) + b'\n')
    (ROOT / 'workshop/description.txt').write_text(description + '\n', encoding='utf-8')
    print(json.dumps(dict(project=str(project_path), content=str(target / 'content'), uploaded=False)))


if __name__ == '__main__':
    main()
