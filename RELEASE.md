# How to create a new release for Flask-FS2

We release Flask-FS2 versions through Github. Every time a new version is ready, we
follow this process:

1. Up the version number located the `flask_fs/__version__.py` file.
2. Rebase on the master branch.
2. Push changes to `master` branch.
3. Build the package from the sources
4. Tag the commit and push the changes to Github
5. Publish the package on Pypi

You can run the following script to perform these commands at once:

```bash
release_number=0.7.0
git pull --rebase origin master
echo "__version__ = \"$release_number\"" > flask_fs/__version__.py
git commit flask_fs/__version__.py -m $release_number
git tag v$release_number
git push origin master --tag
python setup.py bdist_wheel --universal
twine upload dist/flask_fs2-$release_number-py2.py3-none-any.whl
```

# Deployment

Please see the Zou documentation for the update instructions.
