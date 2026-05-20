Changelog
=========

Current
-------

- Swift backend: per-process ``Connection`` pool (``gevent.queue.Queue`` with
  stdlib ``queue.Queue`` fallback) so concurrent greenlets and threads no
  longer share a single ``swiftclient.Connection``. Fixes sporadic 400s,
  ``ConnectionReset`` errors and content corruption observed under
  ``gevent`` workers.
- Swift backend: ``timeout`` and ``retries`` are now passed to every
  ``Connection`` (defaults: 60 s timeout, 5 retries).
- Swift backend: ``write()`` pre-computes ``content_length`` and ``ETag``
  (when content is bytes or a seekable file-like) and verifies the ETag
  returned by Swift; mismatched objects are deleted and the call raises
  ``ClientException`` to prevent silent corruption.
- Swift backend: ``read_chunks()`` releases the borrowed ``Connection``
  back to the pool when the generator is exhausted or ``close()`` is
  called.
- Swift backend: ``list_files()`` uses ``full_listing=True`` so containers
  with more than 10 000 objects are fully enumerated.
- Swift backend: new optional settings ``pool_size`` (default 20),
  ``timeout`` (default 60) and ``retries`` (default 5).

0.7.33 (2026-01-14)
-------------------

- Upgrade GitHub Actions

0.7.32 (2026-01-12)
-------------------

- Drop Python 3.9 support
- Python 3.12 requirements upgrade

0.7.31 (2025-08-19)
-------------------

- Fix CI
- Upgrade requirements

0.7.30 (2025-05-28)
-------------------

- Remove deprecated ``pkg_resources``
- Upgrade requirements

0.7.29 (2025-03-09)
-------------------

- Upgrade requirements
- Update README

0.7.28 (2025-01-10)
-------------------

- Drop support for Python 3.8, add Python 3.13
- Fix Python 3.13 CI
- Fix ``AttributeError: 'GridFS' object has no attribute '_GridFS__collection'``
- Use ``main`` branch in GitHub workflows
- Fix docker compose in GitHub Actions CI
- Run ``autoflake`` and ``black``
- Upgrade requirements

0.7.27 (2024-07-12)
-------------------

- Upgrade requirements

0.7.26 (2024-05-27)
-------------------

- Use wheel of ``flask_mongoengine3`` directly from PyPI
- Fix MongoDB test errors
- Upgrade requirements

0.7.25 (2024-05-07)
-------------------

- Added ``copy()`` method to ``Storage``
- Upgrade requirements

0.7.24 (2024-03-11)
-------------------

- Upgrade requirements

0.7.23 (2023-10-23)
-------------------

- Allow setting multiple backends, encrypted or not
- Added ``create_container``/``create_bucket`` options for Swift and S3
- Ensure server does not serve files outside ``DEBUG`` mode
- Use new ``pytest-flask`` version for CI tests
- Add ``.vscode/settings.json`` for black formatter
- Upgrade Pillow and other requirements

0.7.22 (2023-10-13)
-------------------

- Swift backend refactoring
- Upgrade boto3
- Launch CI build on pull requests and every branch

0.7.21 (2023-10-09)
-------------------

- Allow Flask v3 and newer boto3
- Add Python 3.12 to classifiers and CI matrix
- Use a pytest-flask branch fixing test issues
- Release script exits immediately on non-zero status

0.7.20 (2023-09-28)
-------------------

- Upgrade boto3

0.7.19 (2023-09-18)
-------------------

- Upgrade ``actions/checkout`` to v4
- Disable ``fail-fast`` in CI so jobs finish even on failure
- Cache pip in CI
- Add pre-commit configuration
- Upgrade requirements
- Update README

0.7.18 (2023-09-12)
-------------------

- Switch CI from Travis to GitHub Actions (``ci.yml`` + ``release.yml``)
- Add release script integrated with new workflow
- Add coverage report
- Test against pypy3.10
- Upgrade requirements

0.7.17 (2023-07-25)
-------------------

- Stop encrypting files in memory (stream encryption)
- Upgrade boto3, pymongo and sphinx

0.7.16 (2023-07-13)
-------------------

- Fix tests
- Remove GitHub dependency, add ``python-keystoneclient``

0.7.15 (2023-07-13)
-------------------

- Allow Flask 2.3 in ``setup.cfg``
- Fix Swift tests
- Add tests for ``crypto.py`` and encrypted files in storage
- Upgrade libraries

0.7.14 (2023-05-31)
-------------------

- Fix tests on Flask 2.3
- Fix ``KeyError`` when ``FS_AES256_ENCRYPTED`` is not set
- Fix Travis build

0.7.13 (2023-05-26)
-------------------

- Fix Flask issue with tests

0.7.12 (2023-05-26)
-------------------

- Upgrade libraries

0.7.11 (2023-05-26)
-------------------

- Added file encryption/decryption on put/get (AES256)
- Allow ``cryptography`` from 39.0.2
- Add ``license_file`` in setup
- Add ``launch.json`` for VSCode debugging
- Add issue templates

0.7.10 (2023-03-13)
-------------------

- Create Swift container only if missing
- Fix pip install command for development

0.7.9 (2023-03-03)
------------------

- Added ``read_chunks()`` method on ``Storage``
- Add test ``test_read_chunks``

0.7.8 (2023-03-03)
------------------

- Use Swift ``auth_version`` 3 by default

0.7.7 (2023-02-24)
------------------

- Change options for Swift

0.7.6 (2023-02-09)
------------------

- Use ``app_context()`` when using ``current_app``

0.7.5 (2023-02-06)
------------------

- Fix ``LocalBackend.delete``: use ``self.path`` for destination

0.7.4 (2022-01-24)
------------------

- CGWire will maintain this fork
- Flask-FS2 requires Python 3.7+ and Flask/Werkzeug 2.0.0+
- Remove all code related to Python 2
- Added ``read_chunks()`` operations
- Add region configuration for Swift and S3

0.6.1 (2018-04-19)
------------------

- Fix a race condition on local backend directory creation
- Proper content type handling on GridFS (thanks to @rclement)

0.6.0 (2018-03-27)
------------------

- Added ``copy()`` and ``move()`` operations
- ``delete()`` now supports directories (or prefixes for key/value stores)
- Improve ``metadata()`` ``mime`` handling
- Added explicit ``ImageField.full(external=False)``

0.5.1 (2018-03-12)
------------------

- Fix ``local`` backend ``list_files()`` nested directories handling

0.5.0 (2018-03-12)
------------------

- Added ``metadata`` method to ``Storage`` to retrieve file metadata
- Force ``boto3 >= 1.4.5`` because of API change (lifecycle)
- Drop Python 3.3 support
- Create parent directories when opening a local file in write mode

0.4.1 (2017-06-24)
------------------

- Fix broken packaging for Python 2.7

0.4.0 (2017-06-24)
------------------

- Added backend level configuration ``FS_{BACKEND_NAME}_{KEY}``
- Improved backend documentation
- Use setuptools entry points to register backends.
- Added `NONE` extensions specification
- Added `list_files` to `Storage` to list the current bucket files
- Image optimization preserve file type as much as possible
- Ensure images are not overwritted before rerendering

0.3.0 (2017-03-05)
------------------

- Switch to pytest
- ``ImageField`` optimization/compression.
  Resized images are now compressed.
  Default image can also be optimized on upload with ``FS_IMAGES_OPTIMIZE = True``
  or by specifying `optimize=True` as field parameter.
- ``ImageField`` has now the ability to rerender images with the ``rerender()`` method.

0.2.1 (2017-01-17)
------------------

- Expose Python 3 compatibility

0.2.0 (2016-10-11)
------------------

- Proper github publication
- Initial S3, GridFS and Swift backend implementations
- Python 3 fixes


0.1 (2015-04-07)
----------------

- Initial release
