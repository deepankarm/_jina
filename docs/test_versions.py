from pathlib import Path

from .versionify import VersionManagement

import pytest


@pytest.mark.parametrize(
    'version_in_dir, latest_version, version_in_dropdown, html_filepath, expected',
    [
        # version_in_dir == version_in_dropdown != latest_version
        (
            'master',
            'v1.2.3',
            'master',
            Path('/tmp/abc/master/index.html'),
            'master/index.html',
        ),
        # version_in_dir == version_in_dropdown != latest_version
        (
            'master',
            'v1.2.3',
            'master',
            Path('/tmp/abc/master/fundamentals/document/index.html'),
            'master/fundamentals/document/index.html',
        ),
        # version_in_dir == version_in_dropdown != latest_version
        (
            'v1.2.3',
            'v1.2.4',
            'v1.2.3',
            Path('/tmp/abc/v1.2.3/index.html'),
            'v1.2.3/index.html',
        ),
        # version_in_dir == version_in_dropdown != latest_version
        (
            'v1.2.3',
            'v1.2.4',
            'v1.2.3',
            Path('/tmp/abc/v1.2.3/fundamentals/document/index.html'),
            'v1.2.3/fundamentals/document/index.html',
        ),
        # version_in_dir == version_in_dropdown == latest_version
        (
            'v1.2.3',
            'v1.2.3',
            'v1.2.3',
            Path('/tmp/abc/index.html'),
            'index.html',
        ),
        # version_in_dir == version_in_dropdown == latest_version
        (
            'v1.2.3',
            'v1.2.3',
            'v1.2.3',
            Path('/tmp/abc/fundamentals/document/index.html'),
            'fundamentals/document/index.html',
        ),
        # version_in_dir == latest_version != version_in_dropdown
        (
            'v1.2.3',
            'v1.2.3',
            'master',
            Path('/tmp/abc/index.html'),
            'master/index.html',
        ),
        # version_in_dir == latest_version != version_in_dropdown
        (
            'v1.2.3',
            'v1.2.3',
            'master',
            Path('/tmp/abc/fundamentals/document/index.html'),
            '../../master/fundamentals/document/index.html',
        ),
        # version_in_dir == latest_version != version_in_dropdown
        (
            'v1.2.3',
            'v1.2.3',
            'v1.2.4',
            Path('/tmp/abc/index.html'),
            'v1.2.4/index.html',
        ),
        # version_in_dir == latest_version != version_in_dropdown
        (
            'v1.2.3',
            'v1.2.3',
            'v1.2.4',
            Path('/tmp/abc/fundamentals/document/index.html'),
            '../../v1.2.4/fundamentals/document/index.html',
        ),
        # version_in_dir != latest_version != version_in_dropdown
        (
            'v1.2.3',
            'v1.2.4',
            'master',
            Path('/tmp/abc/v1.2.3/index.html'),
            '../master/index.html',
        ),
        # version_in_dir != latest_version != version_in_dropdown
        (
            'v1.2.3',
            'v1.2.4',
            'master',
            Path('/tmp/abc/v1.2.3/fundamentals/document/index.html'),
            '../../../master/fundamentals/document/index.html',
        ),
        # version_in_dir != version_in_dropdown
        (
            'v1.2.3',
            'v1.2.4',
            'v1.2.4',
            Path('/tmp/abc/v1.2.3/index.html'),
            '../index.html',
        ),
        (
            'v1.2.3',
            'v1.2.4',
            'v1.2.4',
            Path('/tmp/abc/v1.2.3/fundamentals/document/index.html'),
            '../../../fundamentals/document/index.html',
        ),
    ],
)
def test_get_value_for_tag(
    version_in_dir,
    latest_version,
    version_in_dropdown,
    html_filepath,
    expected,
):
    got = VersionManagement.get_value_for_option(
        docsdir='/tmp/abc',
        html_filepath=html_filepath,
        version_in_dropdown=version_in_dropdown,
        version_in_dir=version_in_dir,
        latest_version=latest_version,
    )
    print(got)
    print(expected)
    print(got == expected)
    # )


def test_get_text_for_tag():
    assert (
        VersionManagement.get_text_for_option(
            version_in_dropdown='v1.2.3', latest_version='v1.2.3'
        )
        == 'latest(v1.2.3)'
    )
    assert (
        VersionManagement.get_text_for_option(
            version_in_dropdown='v1.2.3', latest_version='v1.2.4'
        )
        == 'v1.2.3'
    )


def test_is_selected():
    assert VersionManagement.is_option_selected(
        version_in_dropdown='v1.2.3', version_in_dir='v1.2.3'
    )
    assert not VersionManagement.is_option_selected(
        version_in_dropdown='v1.2.3', version_in_dir='v1.2.4'
    )
