set -e
git pull --rebase origin main
last_release_number=$(python -c "from flask_fs import __version__; print(__version__)")
release_number=$(echo ${last_release_number} | awk -F. -v OFS=. '{$NF += 1 ; print}')
echo "__version__ = \"$release_number\"" > flask_fs/__version__.py
git commit flask_fs/__version__.py -m $release_number
git tag v$release_number
git push origin main --tag
