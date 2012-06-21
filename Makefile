tarball:
	rm dist/pcs-gui.tar.gz
	tar -C .. -czvf dist/pcs-gui.tar.gz --exclude ".*" --exclude .git --exclude --exclude=gemhome/*  --exclude=dist pcs-gui

build_gems:
	cd gems; gem install --local -i ../gemhome sinatra sinatra-contrib json highline rack rack-protection tilt eventmachine rack-test backports sinatra-sugar monkey-lib
