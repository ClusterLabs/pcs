PCSD_GEMS=sinatra sinatra-contrib json highline rack rack-protection tilt eventmachine rack-test backports sinatra-sugar monkey-lib rpam-ruby19

tarball:
	rm -f dist/pcsd.tar.gz
	tar -C .. -czvf dist/pcsd.tar.gz --exclude ".*" --exclude .git --exclude --exclude=gemhome/*  --exclude=dist --exclude=assets --exclude=jquery-ui pcs-gui 

build_gems:
	mkdir -p gems; cd gems; gem install --local -i ../gemhome ${PCSD_GEMS}

get_gems:
	mkdir -p gems; cd gems; gem fetch ${PCSD_GEMS}

clean_gems:
	mkdir -p gems; cd gems; rm -f ${PCSD_GEMS}
