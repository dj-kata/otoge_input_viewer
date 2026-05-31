target="otoge_input_viewer"
wuv=/mnt/c/Users/katao/.local/bin/uv.exe

rm -rf "$target"
$wuv run setup.py build
cp -a html/ "$target/"
cp -a version.txt "$target/"
cp "$target"/*.exe to_bin/
cp -a html/ to_bin/
rm -rf "$target.zip"
zip -r "$target.zip" "$target"
