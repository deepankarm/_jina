import os
import sys
import json
import shutil
import logging
import argparse
import subprocess
import urllib.request
from pathlib import Path
from typing import List, Union
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from packaging.version import InvalidVersion, Version

from bs4 import BeautifulSoup


def get_logger():
    logFormatter = logging.Formatter(fmt=' %(name)s:%(levelname)8s: %(message)s')
    logger = logging.getLogger('docs-versioning')
    logger.setLevel(logging.DEBUG)
    consoleHandler = logging.StreamHandler()
    consoleHandler.setLevel(logging.DEBUG)
    consoleHandler.setFormatter(logFormatter)
    logger.addHandler(consoleHandler)
    return logger


logger = get_logger()


class CheckoutBranch(ExitStack):
    """
    Checkout a branch or tag in a temporary directory & cd into that.
    This assumes that the repo is already cloned.
    """

    def __init__(self, repodir: str, branch_or_tag: str = 'gh-pages') -> None:
        super().__init__()
        self.repodir = repodir
        self.branch_or_tag = branch_or_tag

    @staticmethod
    def add_worktree(branch_or_tag, tmpdir):
        subprocess.run(['git', 'worktree', 'add', tmpdir, branch_or_tag])

    @staticmethod
    def remove_worktree(tmpdir):
        subprocess.run(['git', 'worktree', 'remove', tmpdir])

    def __enter__(self):
        self._tmpdir = self.enter_context(TemporaryDirectory())
        self.curdir = os.getcwd()
        os.chdir(self.repodir)
        logger.info(
            f'Creating a temp worktree for `{self.branch_or_tag}` in {self._tmpdir}'
        )
        CheckoutBranch.add_worktree(self.branch_or_tag, self._tmpdir)
        self.docsdir = os.path.join(self._tmpdir, 'docs')
        os.chdir(self.docsdir)
        return self

    def __exit__(self, *args, **kwargs):
        os.chdir(self.curdir)
        self.remove_worktree(self._tmpdir)
        return super().__exit__(*args, **kwargs)


class ClonedDocs(ExitStack):
    def __init__(self, path: str) -> None:
        super().__init__()
        if not os.path.isdir(path):
            raise FileNotFoundError(
                'Invalid docs_path found. Please clone & pass `docs` repo path'
            )
        self.docsdir = path

    def __enter__(self):
        self.curdir = os.getcwd()
        os.chdir(self.docsdir)
        return self

    def __exit__(self, *args, **kwargs):
        os.chdir(self.curdir)
        return super().__exit__(*args, **kwargs)

    @staticmethod
    def commit():
        commands = []
        # if 'GITHUB_WORKFLOW' in os.environ:
        #     print(f'\n\n\n\nHurray: {"GITHUB_TOKEN" in os.environ}\n\n\n')
        #     commands.append(
        #         f'git remote set-url origin https://deepankarm:{os.environ.get("GITHUB_TOKEN")}@github.com/jina-ai/staging-docs.git'
        #     )
        commit_message = os.getenv(
            'COMMIT_MESSAGE', 'chore(docs): update docs due to commit'
        )
        commands.extend(
            [
                'git status',
                'git config --local user.email "deepankar.mahapatro@jina.ai"',
                'git config --local user.name "Deepankar Mahapatro"',
                'git add -A',
                f'git commit -m \"{commit_message}\"',
                'git push --force origin main',
            ]
        )
        [subprocess.run(command, shell=True) for command in commands]


class VersionManagement:
    def __init__(self, args: argparse.Namespace, docsdir: str) -> None:
        self.args = args
        self.docsdir = docsdir
        self._existing_versions = []
        self._non_existing_versions = []
        self.last_n_versions = VersionManagement.get_last_n_versions(
            args.repo, args.num_releases
        )
        self.latest_version = self.last_n_versions[0]

    @property
    def existing_versions(self) -> List:
        return self._existing_versions

    @property
    def non_existing_versions(self) -> List:
        return self._non_existing_versions

    @property
    def dropdown_versions_in_order(self):
        _versions_to_be_added = []
        if not self.args.exclude_default_branch:
            _versions_to_be_added.append(self.args.default_branch_name)
        _versions_to_be_added.extend(self.last_n_versions)
        return _versions_to_be_added

    @staticmethod
    def get_last_n_versions(repo: str, n: int) -> List[str]:
        return [
            version['tag_name']
            for version in json.loads(
                urllib.request.urlopen(
                    f'https://api.github.com/repos/{repo}/releases?per_page={n}'
                )
                .read()
                .decode()
            )
        ]

    @staticmethod
    def build_local_only(version: str = ''):
        assert os.path.isfile(
            os.path.join(os.getcwd(), 'makedoc.sh')
        ), f'makedoc.sh file doesn\'t exist in current directory {os.getcwd()}'

        try:
            if version in ['v2.5.0', 'v2.4.10', 'v2.4.9']:
                f_content = '''import os
os.system('sphinx-build . _build/dirhtml -b dirhtml') # special case for 2.5.0, 2.4.10 & 2.4.9
'''
            else:
                f_content = '''import os
os.system('bash makedoc.sh')
'''
            with open(os.path.join(os.getcwd(), 'exec.py'), 'w') as f:
                f.write(f_content)
            subprocess.run(['python', 'exec.py'], check=True, executable=sys.executable)
        finally:
            os.remove(os.path.join(os.getcwd(), 'exec.py'))

    def build_default_only(self, repodir, gh_page_dir):
        VersionManagement.build_versions(
            versions=self.args.default_branch_name,
            repodir=repodir,
            gh_page_dir=gh_page_dir,
            build_dir=self.args.build_dir,
        )

    def build_latest_only(self, repodir, gh_page_dir):
        VersionManagement.build_versions(
            versions=self.latest_version,
            repodir=repodir,
            gh_page_dir=gh_page_dir,
            build_dir=self.args.build_dir,
        )

    def build_non_existing_versions(self, repodir, gh_page_dir):
        VersionManagement.build_versions(
            versions=self.non_existing_versions,
            repodir=repodir,
            gh_page_dir=gh_page_dir,
            build_dir=self.args.build_dir,
        )

    @staticmethod
    def build_versions(
        versions: Union[str, List[str]], repodir: str, gh_page_dir: str, build_dir: str
    ):
        # git cannot be run with multiple processes.
        if not isinstance(versions, List):
            versions = [versions]

        for version in versions:
            logger.info(f'Asked to rebuild version `{version}`, {os.getcwd()}')
            with CheckoutBranch(repodir=repodir, branch_or_tag=version) as tag:
                # Inside {tmpdir}/docs where `version` is checked out.
                VersionManagement.cleanup_version_directory(gh_page_dir, version)
                VersionManagement.build_local_only(version=version)
                VersionManagement.recreate_version_directory(
                    gh_page_dir, tag, version, build_dir
                )

    @staticmethod
    def cleanup_version_directory(gh_page_docs_dir, version):
        """This removes `version` directory from gh_pages worktree, so it can be rebuilt"""
        shutil.rmtree(os.path.join(gh_page_docs_dir, version), ignore_errors=True)

    @staticmethod
    def recreate_version_directory(
        gh_page_docs_dir, tag: CheckoutBranch, version: str, build_dir: str
    ):
        """This recreates `version` directory in gh_pages worktree, so that it can be committed"""
        shutil.copytree(
            src=os.path.join(tag.docsdir, build_dir),
            dst=os.path.join(gh_page_docs_dir, version),
        )

    def move_latest_version_to_root(self):
        version_dir = os.path.join(self.docsdir, self.latest_version)
        if not os.path.isdir(version_dir):
            logger.warning(
                f'The latest version {self.latest_version} doesn\'t exist, please build first!'
            )
            return
        for content in os.listdir(version_dir):
            old_content_path = os.path.join(self.docsdir, content)
            if os.path.isfile(old_content_path):
                os.remove(old_content_path)
            elif os.path.isdir(old_content_path):
                shutil.rmtree(old_content_path)

            shutil.move(
                src=os.path.join(version_dir, content),
                dst=self.docsdir,
                copy_function=shutil.copytree,
            )
        shutil.rmtree(version_dir)

    def get_versions_status(self):
        """Get already existing versions in the gh-page branch"""
        for dir in os.listdir(self.docsdir):
            num_releases = (
                self.args.num_releases + 1
                if not self.args.exclude_default_branch
                else 0
            )
            if (
                os.path.isdir(os.path.join(self.docsdir, dir))
                and len(self._existing_versions) < num_releases
            ):
                if (
                    not self.args.exclude_default_branch
                    and dir == self.args.default_branch_name
                ):
                    self._existing_versions.append(dir)
                    continue
                elif dir.startswith('v'):  # to avoid 404
                    try:
                        self._existing_versions.append(dir)
                    except InvalidVersion:
                        continue

        _relevant_versions = set(self.last_n_versions)
        if not self.args.exclude_default_branch:
            _relevant_versions.add(self.args.default_branch_name)
        self._non_existing_versions = list(
            _relevant_versions - set(self._existing_versions)
        )

    def update_dropdown_options(self, versions: Union[str, List[str]]):
        """Update select options in already built html files"""

        if not isinstance(versions, List):
            versions = [versions]

        for version_in_dir in versions:
            logger.info(f'Processing files for version {version_in_dir}..')
            for html_filepath in VersionManagement.get_html_filepaths(
                docsdir=self.docsdir,
                version_in_dir=version_in_dir,
                latest_version=self.latest_version,
            ):
                logger.debug(f'Modifying dropdown in path: {html_filepath}')
                with open(html_filepath, 'r') as fp:
                    html = BeautifulSoup(fp.read(), 'html.parser')
                    html_version_dropdown = (
                        VersionManagement._html_get_or_create_dropdown(html)
                    )
                    new_dropdown_options = []
                    for version_in_dropdown in self.dropdown_versions_in_order:
                        kwargs = dict(
                            name='option',
                            value=VersionManagement.get_value_for_option(
                                docsdir=self.docsdir,
                                html_filepath=html_filepath,
                                version_in_dropdown=version_in_dropdown,
                                version_in_dir=version_in_dir,
                                latest_version=self.latest_version,
                            ),
                        )
                        if VersionManagement.is_option_selected(
                            version_in_dropdown=version_in_dropdown,
                            version_in_dir=version_in_dir,
                        ):
                            kwargs.update({'selected': 'selected'})
                        option = html.new_tag(**kwargs)
                        option.string = VersionManagement.get_text_for_option(
                            version_in_dropdown=version_in_dropdown,
                            latest_version=self.latest_version,
                        )
                        new_dropdown_options.append(option)
                    html_version_dropdown.contents = new_dropdown_options
                    html = VersionManagement._html_update_dropdown(
                        html, html_version_dropdown
                    )

                with open(html_filepath, 'w') as fp:
                    fp.write(html.prettify())

    @staticmethod
    def _html_get_or_create_dropdown(html: BeautifulSoup):
        html_version_dropdown = html.find(
            "select", {"class": "version-select"}
        )  # >= v2.4.10
        if not html_version_dropdown:
            html_version_dropdown = html.find("select", {"id": "version"})  # == v2.4.9
        if not html_version_dropdown:
            html_version_dropdown = html.new_tag(
                'select',
                **{
                    'onChange': 'window.location.href=this.value',
                    'class': 'version-select',
                },
            )  # < v2.4.9
            # This can be used to change the properties of the dropdown.
        return html_version_dropdown

    @staticmethod
    def _html_update_dropdown(
        html: BeautifulSoup, html_version_dropdown
    ) -> BeautifulSoup:
        left_side_div = html.find("div", {"class": "sd-text-center"})
        if left_side_div:
            left_side_div.contents = list(
                filter(lambda i: i.name != 'select', left_side_div.contents)
            )  # remove old 'select's
            left_side_div.contents.append(html_version_dropdown)
        return html

    @staticmethod
    def get_html_filepaths(
        docsdir: str,
        version_in_dir: Union[str, Version],
        latest_version: Union[str, Version],
    ):
        if version_in_dir == latest_version:
            versioned_path = Path(docsdir)
            for html_filepath in versioned_path.rglob('*.html'):
                if (
                    html_filepath.relative_to(docsdir)
                    .parts[0]
                    .startswith(('master', 'main', 'v'))
                ):
                    continue
                yield html_filepath
        else:
            versioned_path = Path(docsdir, str(version_in_dir))
            yield from versioned_path.rglob('*.html')

    @staticmethod
    def get_value_for_option(
        docsdir: str,
        html_filepath: Path,
        version_in_dropdown: Union[str, Version],
        version_in_dir: Union[str, Version],
        latest_version: Union[str, Version],
    ) -> str:
        # print(
        #     f'\n\n\n\ndocsdir: {docsdir}\nhtml_filepath: {html_filepath}\nversion_in_dropdown: {version_in_dropdown}'
        #     f'\nversion_in_dir: {version_in_dir}\nlatest_version: {latest_version}'
        # )
        path_relative_to_docroot = html_filepath.relative_to(docsdir)

        if version_in_dir == version_in_dropdown:
            if path_relative_to_docroot.parts[0] == latest_version:
                value = str(Path(*path_relative_to_docroot.parts[1:]))
            else:
                value = str(path_relative_to_docroot)
        else:
            # print(f'in else, {path_relative_to_docroot.parts}')
            if version_in_dir == latest_version:
                rel_path = str(path_relative_to_docroot)
            else:
                rel_path = str(Path(*path_relative_to_docroot.parts[1:]))
            rel_path_len = len(path_relative_to_docroot.parts) - 1
            rel_version = (
                version_in_dropdown if version_in_dropdown != latest_version else ''
            )

            value = ('../' * rel_path_len + rel_version + '/' + rel_path).replace(
                '//', '/'
            )
        return value.rstrip('index.html').rstrip('.html')

    @staticmethod
    def get_text_for_option(
        version_in_dropdown: Union[str, Version], latest_version: Union[str, Version]
    ) -> str:
        return (
            f'latest({str(version_in_dropdown)})'
            if str(version_in_dropdown) == str(latest_version)
            else str(version_in_dropdown)
        )

    @staticmethod
    def is_option_selected(
        version_in_dropdown: Union[str, Version], version_in_dir: Union[str, Version]
    ) -> bool:
        return True if str(version_in_dropdown) == str(version_in_dir) else False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Versions handler')

    parser.add_argument('--repo', default='jina-ai/jina', help='Pass the repo name')
    parser.add_argument(
        '--repodir',
        help='Pass the path to the already cloned repo (jina/finetuner)',
    )
    parser.add_argument(
        '--docsdir',
        help='Pass the path to the already cloned docs repo',
    )

    parser.add_argument(
        '--local-only',
        help='Build local changed only, previous versions won\'t show up in docs',
        default=False,
        action='store_true',
    )
    parser.add_argument(
        '--default-only',
        help='Build & update only the default branch (master/main) branch (Ran during CD)',
        default=False,
        action='store_true',
    )
    parser.add_argument(
        '--latest-only',
        help='Build & update only the latest branch (master/main) branch (Ran during Release)',
        default=False,
        action='store_true',
    )
    parser.add_argument(
        '--num-releases',
        help='Pass the number of versions to be included in the dropdown',
        default=3,
    )

    parser.add_argument(
        '--default-branch-name',
        help='Pass the default branch name (master/main)',
        default='master',
    )
    parser.add_argument(
        '--exclude-default-branch',
        help='False if master/main branch needs to be included in the versions',
        default=False,
        action='store_true',
    )
    parser.add_argument(
        '--build-dir',
        help='Pass the build directory relative to `docs`',
        default='_build/dirhtml',
    )
    parser.add_argument(
        '--commit',
        help='True if changes to gh_pages branch needs to committed and pushed to the docs origin',
        default=False,
        action='store_true',
    )

    args = parser.parse_args()

    if args.local_only:
        manager = VersionManagement(args, docsdir=os.getcwd())
        manager.build_local_only()
    else:
        with ClonedDocs(args.docsdir) as gh_page:
            # Inside already cloned `docs` repo
            manager = VersionManagement(args, gh_page.docsdir)

            if args.default_only:
                manager.build_default_only(args.repodir, gh_page.docsdir)
                manager.update_dropdown_options(manager.args.default_branch_name)
            elif args.latest_only:
                manager.build_latest_only(args.repodir, gh_page.docsdir)
                manager.update_dropdown_options(manager.latest_version)
                manager.move_latest_version_to_root()
            else:
                manager.get_versions_status()
                manager.build_non_existing_versions(args.repodir, gh_page.docsdir)
                manager.update_dropdown_options(manager.dropdown_versions_in_order)
                manager.move_latest_version_to_root()

            if args.commit:
                gh_page.commit()
