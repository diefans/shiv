import os
import sys

from contextlib import contextmanager
from pathlib import Path
from site import addsitedir
from code import interact
from uuid import uuid4
from zipfile import ZipFile

import pytest

from unittest import mock


@contextmanager
def env_var(key, value):
    os.environ[key] = value
    yield
    del os.environ[key]


class TestBootstrap:
    def test_various_imports(self):
        from shiv import bootstrap

        assert bootstrap.import_string('site.addsitedir') == addsitedir
        assert bootstrap.import_string('site:addsitedir') == addsitedir
        assert bootstrap.import_string('code.interact') == interact
        assert bootstrap.import_string('code:interact') == interact

        # test things not already imported
        func = bootstrap.import_string('os.path:join')
        from os.path import join
        assert func == join

        # test something already imported
        import shiv
        assert bootstrap.import_string('shiv') == shiv == sys.modules['shiv']

        # test bogus imports raise properly
        with pytest.raises(ImportError):
            bootstrap.import_string('this is bogus!')

    def test_is_zipfile(self, zip_location):
        from shiv import bootstrap

        with mock.patch.object(sys, 'argv', [zip_location]):
            assert isinstance(bootstrap.current_zipfile(), ZipFile)

    # When the tests are run via tox, sys.argv[0] is the full path to 'pytest.EXE',
    # i.e. a native launcher created by pip to from console_scripts entry points.
    # These are indeed a form of zip files, thus the following assertion could fail.
    @pytest.mark.skipif(os.name == 'nt', reason="this may give false positive on win")
    def test_argv0_is_not_zipfile(self):
        from shiv import bootstrap

        assert not bootstrap.current_zipfile()

    def test_cache_path(self):
        from shiv import bootstrap

        mock_zip = mock.MagicMock(spec=ZipFile)
        mock_zip.filename = "test"
        uuid = str(uuid4())

        assert bootstrap.cache_path(mock_zip, Path.cwd(), uuid) == Path.cwd() / f"test_{uuid}"

    def test_first_sitedir_index(self):
        from shiv import bootstrap

        with mock.patch.object(sys, 'path', ['site-packages', 'dir', 'dir', 'dir']):
            assert bootstrap._first_sitedir_index() == 0

        with mock.patch.object(sys, 'path', []):
            assert bootstrap._first_sitedir_index() is None


class TestEnvironment:
    def test_overrides(self):
        from shiv.bootstrap.environment import Environment

        env = Environment()

        assert env.entry_point is None
        with env_var('SHIV_ENTRY_POINT', 'test'):
            assert env.entry_point == 'test'

        assert env.interpreter is None
        with env_var('SHIV_INTERPRETER', '1'):
            assert env.interpreter is not None

        assert env.root is None
        with env_var('SHIV_ROOT', 'tmp'):
            assert env.root == Path('tmp')

        assert env.force_extract is False
        with env_var('SHIV_FORCE_EXTRACT', '1'):
            assert env.force_extract is True

    def test_serialize(self):
        from shiv.bootstrap.environment import Environment

        env = Environment()
        env_as_json = env.to_json()
        env_from_json = Environment.from_json(env_as_json)
        assert env.__dict__ == env_from_json.__dict__


@mock.patch('shiv.bootstrap.shutil')
@pytest.mark.parametrize('compile_pyc, call_arg_list', [
    (True, [mock.call(Path('foo/bar.tmp'), quiet=2, workers=0)]),
    (False, []),
])
def test_extract_site_packages(mock_shutil, compile_pyc, call_arg_list):
    from shiv import bootstrap

    mock_archive = mock.Mock()
    mock_archive.namelist.return_value = ['site-packages/foo', 'something/bar']

    with mock.patch.object(bootstrap, 'compileall') as mock_compileall:
        bootstrap.extract_site_packages(mock_archive, Path('foo/bar'),
                                        compile_pyc=compile_pyc)

    mock_archive.extract.assert_called_once_with(
        'site-packages/foo', Path('foo/bar.tmp'))

    assert mock_compileall.compile_dir.call_args_list == call_arg_list
    mock_shutil.move.assert_called_with('foo/bar.tmp', 'foo/bar')
