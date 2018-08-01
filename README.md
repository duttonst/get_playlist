# get_playlist.py is a Python script which:

- Scrapes the list of tracks on an iTunes podcast e.g. Chicane Sun:Sets podcasts at https://itunes.apple.com/gb/podcast/chicane-presents-sun-sets/id745185047?mt=2
- Parses out the names of the tracks
- Tries to find each track in Apple Music
- Spits-out an HTML file which makes it easy to add each found track to your iTunes library

I would have liked to add the tracks to iTunes programmatically but I failed to find a way to do this from Python

Usage:

# ./get_playlist.py
