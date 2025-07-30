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

clean:
	@rm -rf $(target)
	@rm -rf $(outdir)/update.exe
	@rm -rf __pycache__

test:
	@$(wuv) run otoge_input_viewer.pyw
