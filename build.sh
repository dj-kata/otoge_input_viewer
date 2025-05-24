target="otoge_input_viewer"
pyin=/mnt/c/*/Python310/Scripts/pyinstaller.exe
$pyin $target.pyw --clean --noconsole --onefile --icon=icon.ico --add-data "icon.ico;./" 
cp *.html $target/
cp dist/*.exe to_bin/
cp *.html to_bin/
cp dist/*.exe $target/
cp version.txt $target/
#zip $target.zip $target/* $target/*/* $target/*/*/*
rm -rf $target.zip
#zip $target.zip $target/* $target/*/* 
zip $target.zip $target/* 
