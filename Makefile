wuv=/mnt/c/Users/katao/.local/bin/uv.exe
main_file_name=otoge_input_viewer
project_name=otoge_input_viewer
build_stamp=$(project_name)/.built
target_zip=$(project_name).zip
srcs=$(wildcard *.py) $(wildcard *.pyw) $(wildcard src/*.py) src/icon.ico
html_files=$(wildcard html/*.*)
ZIP ?= 7z a -tzip -mx=1 -mmt=on

.PHONY: all build zip dist clean test
.DELETE_ON_ERROR:

all: zip

build: $(build_stamp)

zip: $(target_zip)

$(target_zip): $(build_stamp)
	@rm -rf $(target_zip)
	@rm -rf $(project_name)/log
	@rm -f $(project_name)/oiv_conf.pkl $(project_name)/html/oiv_conf.pkl
	@rm -f $(project_name)/history.oiv $(project_name)/html/history.oiv
	@$(ZIP) $(target_zip) $(project_name)

$(build_stamp): $(srcs) $(html_files) version.txt setup.py pyproject.toml uv.lock
	@rm -rf $(project_name)
	@$(wuv) run setup.py build
	@echo "不要なファイルを削除中..."
	@rm -f $(project_name)/lib/PySide6/Qt6WebEngine*.dll 2>/dev/null || true
	@rm -rf src/*.egg-info $(project_name)/lib/src/*.egg-info
	@rm -f $(project_name)/oiv_conf.pkl $(project_name)/html/oiv_conf.pkl
	@rm -f $(project_name)/history.oiv $(project_name)/html/history.oiv
	@touch $(build_stamp)

dist: build
	@cp -a html to_bin/
	@cp -a version.txt to_bin/
	@cp -a $(project_name)/*.exe to_bin/

clean:
	@rm -rf $(project_name) $(target_zip)
	@rm -rf __pycache__
	@rm -rf src/__pycache__ src/*.egg-info qt.conf

test:
	@$(wuv) run python $(main_file_name).pyw
