wuv ?= /mnt/c/Users/katao/.local/bin/uv.exe
outdir=otoge_input_viewer
target=$(outdir)/.built
target_zip=otoge_input_viewer.zip
srcs=$(wildcard *.py) $(wildcard *.pyw) $(wildcard src/*.py) src/icon.ico
html_files=$(wildcard html/*.*)
ZIP ?= 7z a -tzip -mx=1 -mmt=on

all: $(target_zip)
$(target_zip): $(target) $(html_files) version.txt
	@rm -rf $(target_zip)
	@cp version.txt $(outdir)
	@cp -a html $(outdir)
	@rm -rf $(outdir)/log
	@$(ZIP) $(target_zip) $(outdir)

$(target): $(srcs) $(html_files) version.txt setup.py
	@rm -rf $(outdir)
	@$(wuv) run setup.py build
	@rm -f $(outdir)/lib/PySide6/Qt6WebEngine*.dll 2>/dev/null || true
	@rm -rf src/*.egg-info $(outdir)/lib/src/*.egg-info
	@touch $(target)

dist: 
	@cp -a html to_bin/
	@cp -a version.txt to_bin/
	@cp -a $(outdir)/*.exe to_bin/

clean:
	@rm -rf $(outdir)
	@rm -rf __pycache__
	@rm -rf src/__pycache__ src/*.egg-info qt.conf

test:
	@$(wuv) run python otoge_input_viewer.pyw
