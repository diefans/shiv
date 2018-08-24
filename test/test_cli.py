import os
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from shiv.cli import main
from shiv.constants import (BLACKLISTED_ARGS, DISALLOWED_PIP_ARGS, NO_OUTFILE,
                            NO_PIP_ARGS)


def strip_header(output):
    return '\n'.join(output.splitlines()[1:])


class TestCLI:
    @pytest.fixture
    def runner(self):
        return lambda args: CliRunner().invoke(main, args)

    def test_no_args(self, runner):
        result = runner([])
        assert result.exit_code == 1
        assert strip_header(result.output) == NO_PIP_ARGS

    def test_no_outfile(self, runner):
        result = runner(['-e', 'test', 'flask'])
        assert result.exit_code == 1
        assert strip_header(result.output) == NO_OUTFILE

    @pytest.mark.parametrize("arg", [arg for tup in BLACKLISTED_ARGS.keys() for arg in tup])
    def test_blacklisted_args(self, runner, arg):
        result = runner(['-o', 'tmp', arg])

        # get the 'reason' message:
        for tup in BLACKLISTED_ARGS:
            if arg in tup:
                reason = BLACKLISTED_ARGS[tup]

        assert result.exit_code == 1

        # assert we got the correct reason
        assert strip_header(result.output) == DISALLOWED_PIP_ARGS.format(arg=arg, reason=reason)

    def test_hello_world(self, tmpdir, runner, package_location):

        with tempfile.TemporaryDirectory(dir=tmpdir) as tmpdir:
            output_file = Path(tmpdir, 'test.pyz')

            result = runner(['-e', 'hello:main', '-o', str(output_file), str(package_location)])

            # check that the command successfully completed
            assert result.exit_code == 0

            # ensure the created file actually exists
            assert output_file.exists()

            # now run the produced zipapp
            with subprocess.Popen([str(output_file)], stdout=subprocess.PIPE, shell=True) as proc:
                assert proc.stdout.read().decode() == "hello world" + os.linesep

    @mock.patch('shiv.cli.pip')     # just to speedup tests
    def test_no_compile_pyc(self, mock_pip,
                            runner, tmpdir, package_location):
        import json
        with tempfile.TemporaryDirectory(dir=tmpdir) as tmpdir:
            output_file = Path(tmpdir, 'test.pyz')

            with mock.patch('shiv.cli.Path.write_text') as mock_write_text, \
                    mock.patch('shiv.cli.uuid.uuid4') as mock_uuid4:
                mock_uuid4.return_value = 'foo'
                runner(['--no-compile-pyc', '-o', str(output_file),
                        str(package_location)])

                mock_write_text.assert_called_with(json.dumps({
                    "build_id": "foo",
                    "always_write_cache": False,
                    "compile_pyc": False,
                    "entry_point": None
                }))
