#! /bin/bash

# This script assumes none of the dotfiles that are to be replaced are 
# symlinks

BACKUPDIR="$HOME/.dotfilebak"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}"  )" && pwd  )"

function backup_old {
	TARGET=$1
	mkdir -p "${BACKUPDIR}"

	if [ -e $TARGET -a ! -L $TARGET ]; then
		mv $TARGET "$BACKUPDIR/$(basename $TARGET)"
	fi
}

for d in $DIR/*; do
    # iterate only over directories
    [ ! -d $d ] && continue

    for entry in $d/*; do
	    TARGET="${HOME}/.$(basename $entry)"
	    backup_old $TARGET
	    if [ -L $TARGET ]; then
		    # skip existing links. 
		    continue
	    fi
	    ln -s $entry "${HOME}/.$(basename $entry)"
    done
done

# delete old / stale links
for x in ~/.[!.]*; do 
	if [ -L "$x"  ] && ! [ -e "$x"  ]; then 
		echo "removing $x"
		rm -- "$x"; 
	fi; 
done

