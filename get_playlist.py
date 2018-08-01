#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# from urllib.parse import urlencode
# from urllib.request import urlopen

from urllib import urlopen
from urllib import urlencode

import time
import sys
import json
import datetime
import argparse

from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from xml.etree import ElementTree
from xml.dom import minidom

from bs4 import BeautifulSoup

class Track:

    def __init__(self, vol, trackname):

        try:
            self.volume = int(vol)
        except:
            self.volume = 999

        t1 = trackname.find(" ")
        t2 = trackname.find("-")
        t3 = trackname.rfind("(")
        t4 = trackname.rfind(")")
        t5 = len(trackname)
        if t2 == -1:
            t2 = t1
        self.trackno = int(trackname[0:t1].strip().strip('.'))
        a = ""
        if t3 >= t2 and t4 >= t3: # the track name includes a "mix"
            self.name = trackname[t2 + 1:t3].strip()
            self.mix = trackname[t3 + 1:t4].strip()
            a = trackname[t1:t2].strip()
        else:
            self.name = trackname[t2 + 1:t5].strip()
            self.mix = ""
            a = trackname[t1:t2].strip()

        a = a.replace(" ft "," featuring ")
        a = a.replace(" feat "," featuring ")
        a = a.replace(" ft. "," featuring ")
        a = a.replace(" feat. "," featuring ")
        a = a.replace(", "," featuring ")
        a = a.replace("& "," featuring ")
        t6 = a.find("featuring")

        if t6 >= 0: # there's more than one artist specified
            self.artist = a[0:t6].strip()
            self.featured = a[t6+9:t5].strip()
        else:
            self.artist = a
            self.featured = ""
        self.raw = trackname
        self.shortname = "%s - %s" % (self.name, self.artist)
        self.sortkey = ("%04d%03d" % (self.volume, self.trackno)).encode('ascii')
        self.itunes = None

    def lookup(self):

        # First build up a list of candidate tracks by calling the iTunes API
        track_candidates = {}
        ar = web_query_string(self.artist)
        fr = "+" + web_query_string(self.featured)
        tr = web_query_string(self.name)
        mr = "+" + web_query_string(self.mix)

        for matchType in ((True, True, True),
                          (True, False, True),
                          (False, True, True),
                          (False, False, True),
                          (True, True, False),
                          (True, False, False),
                          (False, True, False),
                          (False, False, False)
                          ):
            tight_match_track = matchType[0]
            tight_match_artist = matchType[1]
            search_by_artist_not_song = matchType[2]

            if search_by_artist_not_song:
                # API allows search by artist or song; the former gets better results in practice so use this first
                if tight_match_artist: # include second artist in the search term (if there is one)
                    if fr == "+": continue # optimisation: don't bother as there's no featured artist
                    match_args = {"entity": "song", "attribute": "artistTerm", "media": "music", "country": "gb",
                             "app": "music", "limit": "200", "term": ar + fr}
                else:
                    match_args = {"entity": "song", "attribute": "artistTerm", "media": "music", "country": "gb",
                             "app": "music", "limit": "200", "term": ar}
            else:
                # Search iTunes by song name
                if tight_match_artist: # include second artist in the search term (if there is one)
                    if mr == "+": continue # optimisation: don't bother as there's no mix
                    match_args = {"entity": "song", "attribute": "songTerm", "media": "music", "country": "gb",
                             "app": "music", "limit": "200", "term": tr + mr}
                else:
                    match_args = {"entity": "song", "attribute": "songTerm", "media": "music", "country": "gb",
                             "app": "music", "limit": "200", "term": tr}

            url = "https://itunes.apple.com/search?{}".format(urlencode(match_args))
            try:
                itunes = urlopen(url).read()

            except:
                print("*** iTunes API call barfed with error: [%s] on url [%s]" % (sys.exc_info()[0], url))
                # try once more
                try:
                    time.sleep(10)
                    itunes = urlopen(url).read()

                except:
                    print("Giving up and moving on")
                    continue

            time.sleep(3)
            j = json.loads(itunes.decode("utf-8"))

            if j["resultCount"] > 0:
                for a in j['results']:
                    if a["isStreamable"]: # ignore if not apple music streamable
                        if flexi_match(self.artist, a["artistName"], tight_match_artist):
                            if flexi_match(self.name, a["trackCensoredName"], tight_match_track):
                                    track_candidates.update({a["trackId"]: a})

            if len(track_candidates) > 0:
                break

        # now we (hopefully) have a list of candidates, so pick the best one
        if len(track_candidates) == 0:
            print("Failed to find [%s]='%s'" % (self.artist, self.name))
        else:
            self.itunes = None

            for a in track_candidates.values():
                if not "collectionName" in a:
                    self.itunes = a
                    break

            if self.itunes is None:
                for a in track_candidates.values():
                    if flexi_match(self.name, a["collectionName"], True):
                        self.itunes = a
                        break

            if self.itunes is None:
                for a in track_candidates.values():
                    if flexi_match(self.name, a["collectionName"], False):
                        self.itunes = a
                        break

            if self.itunes is None:
                for a in track_candidates.values():
                    if a["collectionName"].upper().find("SINGLE") >= 0:
                        self.itunes = a
                        break

            if self.itunes is None:
                for a in track_candidates.values():
                    if a["collectionName"].upper().find(" EP") >= 0:
                        self.itunes = a
                        break

            if self.itunes is None:
                for a in track_candidates.values():
                    if a["collectionName"].upper().find("RADIO EDIT") >= 0:
                        self.itunes = a
                        break

            if self.itunes is None:
                for a in track_candidates.values():
                    self.itunes = a
                    break

            if self.itunes is None:
                for a in track_candidates.values():
                    print("Failed to find a match candidate [%s]='%s' from '%s' with [%s]='%s'" % (a["artistName"], a["trackName"], a["collectionName"], self.artist, self.name))
            else:
                if "collectionName" in self.itunes:
                    print("Matched [%3d#%2d] [%s]='%s' with [%s]='%s' from '%s'" % (self.volume, self.trackno, self.artist, self.name, self.itunes["artistName"], self.itunes["trackName"], self.itunes["collectionName"]))
                else:
                    print("Matched [%3d#%2d] [%s]='%s' with [%s]='%s'" % (self.volume, self.trackno, self.artist, self.name, self.itunes["artistName"], self.itunes["trackName"]))

    def skip(self):
        if self.trackno == 1 or self.name.find("Soundtrack Selection") > -1:
            return True
        else:
            return False


def flexi_match(look_for_string, in_this_string, hard_match=False):
    str1 = de_punctuate(look_for_string.upper().strip())
    str2 = de_punctuate(in_this_string.upper().strip().replace(" ", ""))

    if str1.replace(" ", "") == str2:  # exact match
        return True

    if hard_match:  # all look_for_string strings must be found in in_this_string string

        if (len(str2) - len(str1.replace(" ", ""))) > 4:
            return False  # length gap too big

        has_matched = False
        for t in str1.split():
            if len(t) >= 4:
                if str2.find(t) >= 0:
                    has_matched = True
                else:
                    return False
        return has_matched
    else:  # at least one look_for_string string must be found in in_this_string string
        terms = str1.split()
        match_terms = len(terms)
        if match_terms == 0: match_terms = 1

        m = 0
        for t in terms:
            if str2.find(t) >= 0:
                m += 1
            if m >= match_terms:
                return True
    return False


def de_punctuate(str1):
    ret = str1.replace(".", "")
    ret = ret.replace("&", "")
    ret = ret.replace("-", "")
    ret = ret.replace("'s", "")
    ret = ret.replace("?", "")
    ret = ret.replace("!", "")
    ret = ret.replace("(", "")
    ret = ret.replace(")", "")
    ret = ret.replace("[", "")
    ret = ret.replace("]", "")
    return ret


def web_query_string(str1):
    str2 = de_punctuate(str1)
    str2 = str2.strip().replace(" ", "+")
    return unicode(str2).encode('utf-8')


def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def get_itunes_playlist(itunes_url):
    uniquetracks = {}

    # Get playlist page from iTunes
    fd = urlopen(itunes_url).read()
    fd = fd.decode('utf-8')
    soup = BeautifulSoup(fd, "html.parser")
    trs = soup.find_all("tr", {"class", "podcast-episode"})

    # Parse all the tracks into a list where each only appears once
    for tr in trs:
        title = tr['preview-title'].split()
        vol = title[len(title) - 1]
        tds = tr.find_all("td", {"class", "description flexible-col"})
        for td in tds:
            tracklist = td['sort-value']
            if tracklist != "":
                tracknames = tracklist.split('\n')
                for trackname in tracknames:
                    n = trackname.strip()
                    if n != '':
                        if n[0].isnumeric():
                            t = Track(vol, n)
                            if t.shortname not in uniquetracks:
                                if not t.skip():
                                    uniquetracks.update({t.shortname: t})
#                            else:
#                                print("%s is a dupe" % t.shortname)

    return_list = []
    for t in uniquetracks.values():
        return_list.append(t)

    return return_list

def export_spotty(list_of_tracks, output_filename):
    spottyf = ''
    for t in list_of_tracks:
        if t.mix is not '':
            specification = '%s (%s)' % (t.name, t.mix)
        else:
            specification = t.name

        if t.featured is not '':
            contributor = '%s, %s' % (t.artist, t.featured)
        else:
            contributor = t.artist

        specification = unicode(specification).encode('utf-8')
        contributor = unicode(contributor).encode('utf-8')

        spottyf += '%s – %s\n' % (specification, contributor)

    with open(output_filename, 'w+') as f:
        f.write(spottyf)

    return True



def export_csv(list_of_tracks, output_filename):
    csvf = ''
    for t in list_of_tracks:
        if t.itunes is not None:
            csvf += '"%s","%s"\n' % (t.itunes["trackName"], t.itunes["artistName"])

    with open(output_filename, 'w+') as f:
        f.write(csvf)

    return True


def export_html(list_of_tracks, output_filename):
    root = Element('html')
    table = SubElement(root, 'table')

    for t in list_of_tracks:
        if t.itunes is not None:
            tr = SubElement(table, 'tr')
            td = SubElement(tr, 'td')
            a = SubElement(td, 'a')
            a.text = "Vol %3d: %s" % (t.volume, t.raw)
            a.set("href", t.itunes["trackViewUrl"].replace("https://", "itms://"))

    with open(output_filename, 'w+') as f:
        f.write(tostring(root).decode('utf-8'))

    return True


def export_playlist(list_of_tracks, output_filename):
    top = Element('plist')
    top.set("version", "1.0")
    root_dict = SubElement(top, 'dict')
    SubElement(root_dict, 'key').text = "Major Version"
    SubElement(root_dict, 'integer').text = "1"
    SubElement(root_dict, 'key').text = "Minor Version"
    SubElement(root_dict, 'integer').text = "1"
    SubElement(root_dict, 'key').text = "Application Version"
    SubElement(root_dict, 'string').text = "12.7.2.58"
    SubElement(root_dict, 'key').text = "Tracks"
    tracks_dict = SubElement(root_dict, 'dict')
    SubElement(root_dict, 'key').text = "Playlists"
    tracks_array = SubElement(root_dict, 'array')
    playlist_dict = SubElement(tracks_array, 'dict')
    SubElement(playlist_dict, 'key').text = "Name"
    SubElement(playlist_dict, 'string').text = "Podcast Playlist"
    SubElement(playlist_dict, 'key').text = "Description"
    SubElement(playlist_dict, 'string').text = "Podcast Playlist " + datetime.datetime.now().strftime('%d-%b-%Y')
    SubElement(playlist_dict, 'key').text = "Playlist ID"
    SubElement(playlist_dict, 'integer').text = "123456"
    SubElement(playlist_dict, 'key').text = "All Items"
    SubElement(playlist_dict, 'true')
    SubElement(playlist_dict, 'key').text = "Playlist Items"
    playlist_array = SubElement(playlist_dict, 'array')

    for t in list_of_tracks:
        if t.itunes is not None:
            track_id = str(t.itunes["trackId"])
            album = ""
            if "collectionName" in t.itunes:
                album = t.itunes["collectionName"]

            SubElement(tracks_dict, 'key').text = track_id
            track_attr = SubElement(tracks_dict, 'dict')

            fieldmap = {"Track ID": [track_id, "integer"],
                        "Name": [t.itunes["trackName"], "string"],
                        "Artist": [t.itunes["artistName"], "string"],
                        "Album Artist": ["", "string"],
                        "Album": [album, "string"],
                        "Genre": [t.itunes["primaryGenreName"], "string"],
                        "Kind": ["Apple Music AAC audio file", "string"],
                        "Size": ["", "integer"],
                        "Total Time": [t.itunes["trackTimeMillis"], "integer"],
                        "Disc Number": [t.itunes["discNumber"], "integer"],
                        "Disc Count": ["", "integer"],
                        "Track Number": [t.itunes["trackNumber"], "integer"],
                        "Track Count": [t.itunes["trackCount"], "integer"],
                        "Year": [t.itunes["releaseDate"][:4], "integer"],
                        "Date Modified": ["", "date"],
                        "Date Added": ["", "date"],
                        "Bit Rate": ["", "integer"],
                        "Sample Rate": ["", "integer"],
                        "Release Date": [t.itunes["releaseDate"], "date"],
                        "Artwork Count": ["", "integer"],
                        "Sort Album": [album, "string"],
                        "Sort Artist": [t.itunes["artistName"], "string"],
                        "Sort Name": [t.itunes["trackName"], "string"],
                        "Persistent ID": ["", "string"],
                        "Track Type": ["Remote", "string"],
                        "Apple Music": [None, "true"],
                        "Playlist Only": [None, "true"]}

            for f in fieldmap.keys():
                if fieldmap[f][0] != "":
                    SubElement(track_attr, 'key').text = f
                    if fieldmap[f][0] is None:
                        SubElement(track_attr, fieldmap[f][1])
                    else:
                        SubElement(track_attr, fieldmap[f][1]).text = str(fieldmap[f][0])

            track_attr = SubElement(playlist_array, 'dict')
            SubElement(track_attr, 'key').text = "Track ID"
            SubElement(track_attr, 'integer').text = track_id

    h1 = '<?xml version="1.0" encoding="UTF-8" ?>\n'
    h1 += '<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'

    plfile = open(output_filename, "w")
    plfile.write(h1 + tostring(top).decode('utf-8'))
    plfile.close()
    # print(prettify(top))
    # print(tostring(top))

    return True

# Starts here
parser = argparse.ArgumentParser()

# Optional argument
parser.add_argument('-f', '--first', type=int, default=180,help='Starting track')
parser.add_argument('-p', '--prefix', type=str, default='podcast_pl',help='Output file prefix')
parser.add_argument('-u', '--url', type=str, default='https://itunes.apple.com/gb/podcast/chicane-presents-sun-sets/id745185047?mt=2',help='URL at which to find playlist')


# Switch
parser.add_argument('-s', '--spotify', action='store_true', help='Will export a file in Spotify format before calling Apple Music')
parser.add_argument('-sx', '--spotify-exit', action='store_true', help='Will export a file in Spotify format, then quits')

args = parser.parse_args()
output_spotify = args.spotify
quit_after_spotify = args.spotify_exit
start_vol = args.first
file_stem = args.prefix
pl_url = args.url

print("Getting podcast playlist...")
tracklist = get_itunes_playlist(pl_url)

# Sort tracks by volume & track no
tracklist.sort(key=lambda w: w.sortkey)

# Export in Spotify text format, pre-lookup
if output_spotify or quit_after_spotify:
    export_spotty(tracklist, file_stem + '.txt')

if quit_after_spotify:
    exit(0)

print("Looking up tracks...")
count = 0
# Now look up each track in the volume range we are interested in
for t in tracklist:
    if t.volume >= start_vol:
        t.lookup()
        count += 1

print("Exporting files...")
# generate a web page
export_html(tracklist, file_stem + '.html')

# generate a csv
export_csv(tracklist, file_stem + '.csv')

# generate an iTunes playlist (only works if songs already in library!)
export_playlist(tracklist, file_stem + '.xml')

print("Done")
