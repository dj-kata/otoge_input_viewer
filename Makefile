wuv=/mnt/c/Users/katao/.local/bin/uv.exe
outdir=otoge_input_viewer
target=$(outdir)/otoge_input_viewer.exe
srcs=$(subst update.py,,$(wildcard *.py)) $(wildcard *.pyw)


all: $(target) $(outdir)/update.exe
$(target): $(srcs)
	@$(wuv) run pyarmor -d gen --output=$(outdir) --pack onefile otoge_input_viewer.pyw
	@cp version.txt $(outdir)
	@cp -a html $(outdir)
$(outdir)/update.exe: update.py
	@$(wuv) run pyarmor -d gen --output=$(outdir) --pack onefile $<

dist: 
	@cp -a html to_bin/
	@cp -a version.txt to_bin/
	@cp -a $outdir/*.exe to_bin/

clean:
	@rm -rf $(target)
	@rm -rf $(outdir)/update.exe
	@rm -rf __pycache__
	@rm -rf pyarmor*log

test:
	@$(wuv) run otoge_input_viewer.pyw
