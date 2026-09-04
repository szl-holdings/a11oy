from __future__ import annotations

from pathlib import Path


path = Path(__file__).with_name("materialize_series_a_stop_world_restart.py")
source = path.read_text(encoding="utf-8")
opening = '    helpers = anchor + """\n'
closing = '    return record\n"""\n    source = replace_once('
if source.count(opening) != 1:
    raise SystemExit("materializer helper opening delimiter drifted")
if source.count(closing) != 1:
    raise SystemExit("materializer helper closing delimiter drifted")
source = source.replace(opening, "    helpers = anchor + '''\n", 1)
source = source.replace(
    closing,
    "    return record\n'''\n    source = replace_once(",
    1,
)
path.write_text(source, encoding="utf-8")
