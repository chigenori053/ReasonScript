"""Legacy CLI argument interpretation, including permissive edge cases."""
from pathlib import Path
import pytest
from toolchain.cli_args import option_value, path_arg


@pytest.mark.parametrize('args,expected', [
    ([], None),
    (['--json'], None),
    (['--out'], None),
    (['--out','a'], 'a'),
    (['--out','a','--out','b'], 'a'),
    (['--out','--json'], '--json'),
])
def test_option_value_keeps_first_occurrence(args,expected):
    assert option_value(args,'--out') == expected


@pytest.mark.parametrize('args,value_options,expected', [
    ([], ('--out',), None),
    (['--out'], ('--out',), None),
    (['--out','destination','source'], ('--out',), 'source'),
    (['--json','--skip-tests','source'], ('--out',), 'source'),
    (['--out','--json','source'], ('--out',), 'source'),
    (['--unknown','value','source'], ('--out',), 'value'),
    (['-relative'], ('--out',), '-relative'),
    (['--task','work','--status','VALIDATED','source'], ('--task','--status'), 'source'),
])
def test_path_arg_preserves_flag_and_value_consumption(args,value_options,expected):
    default = Path('default-root')
    assert path_arg(args,default,value_options=value_options) == (default if expected is None else Path(expected))
