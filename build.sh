target="otoge_input_viewer"
rm -rf $target
mkdir $target
mkdir -p $target
pyin=/mnt/c/*/Python310/Scripts/pyinstaller.exe
$pyin $target.pyw --clean --noconsole --onefile --icon=icon.ico --add-data "icon.ico;./" 
cp *.ico $target
cp -a html/ $target/
cp dist/*.exe to_bin/
cp -a html/ to_bin/
cp dist/*.exe $target/
cp version.txt $target/
#zip $target.zip $target/* $target/*/* $target/*/*/*
rm -rf $target.zip
zip $target.zip $target/*  $target/*/*
