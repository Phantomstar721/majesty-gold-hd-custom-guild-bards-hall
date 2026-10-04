# Building Bards Hall from source

The public repository contains code and text configuration. It deliberately
does not contain the private sprites, building artwork, icons, effect art,
recordings, indexed handoffs or approval/reference bundles required to build
the complete playable package. Obtain the playable mod through Workshop.

For development, the build requires a local Majesty Gold HD installation with
its SDK and `Gplbcc.exe`, Python with Pillow, the matching Majesty Mod Manager
source/runtime tooling, and the private asset bundles. The builder reads stock
resources from the developer's installed game; stock game files are not shipped
in the source repository.

With those inputs available:

```powershell
python src/build_bards_hall.py --game-path "PATH\TO\Majesty HD" --output dist/CustomGuildBards
python src/validate_bards_hall.py --game-path "PATH\TO\Majesty HD" dist/CustomGuildBards
python -m unittest discover -s tests -q
```

The PowerShell wrapper `scripts/Build-BardsHall.ps1` uses the workspace's shared
Python installation. Builders emit only the mod's own source package. Players
prepare compatible profiles and launch through Majesty Mod Manager.

The test suite includes behavioral GPL fixtures and stock-relative resource
checks. Tests that inspect original media, private handoffs or a local SDK need
those inputs; the public source alone does not supply them.

## Layout

```text
docs/        Public technical documentation
release/     Player launcher instructions
scripts/     Build and packaging tools
src/         Package builders, configurations and authored GPL
tests/       Behavior and stock-contract checks
```

Generated packages, the original assets and the private development history are
not part of the public source distribution.
