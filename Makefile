tarball:
	rm -f dist/pcsd.tar.gz
	tar -C .. -czvf dist/pcsd.tar.gz --exclude ".*" --exclude .git --exclude --exclude=gemhome/*  --exclude=dist --exclude=assets --exclude=jquery-ui pcs-gui 

build_gems:
	cd gems; gem install --local -i ../gemhome sinatra sinatra-contrib json highline rack rack-protection tilt eventmachine rack-test backports sinatra-sugar monkey-lib
