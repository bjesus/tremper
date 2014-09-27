#!/usr/bin/env python2
# -*- coding: utf-8 -*

from flask import Flask, render_template
import facebook, urllib, subprocess, urlparse, csv, re, arrow, ConfigParser


config = ConfigParser.SafeConfigParser()
config.read('config.cfg')

app = Flask(__name__)
app.jinja_env.add_extension('pyjade.ext.jinja.PyJadeExtension')

app.debug = True

FACEBOOK_APP_ID     = config.get('Facebook', 'APP_ID')
FACEBOOK_APP_SECRET = config.get('Facebook', 'APP_SECRET')

@app.route("/")
def hello():

    searching = []
    offering = []
    not_sure = []
    # Get OAuth Token


    oauth_args = dict(client_id     = FACEBOOK_APP_ID,
                      client_secret = FACEBOOK_APP_SECRET,
                      grant_type    = 'client_credentials')
    oauth_curl_cmd = ['curl',
                      'https://graph.facebook.com/oauth/access_token?' + urllib.urlencode(oauth_args)]
    oauth_response = subprocess.Popen(oauth_curl_cmd,
                                      stdout = subprocess.PIPE,
                                      stderr = subprocess.PIPE).communicate()[0]

    try:
        oauth_access_token = urlparse.parse_qs(str(oauth_response))['access_token'][0]
    except KeyError:
        print('Unable to grab an access token!')
        exit()


    phonePattern = re.compile(r'''
        (\d{3})     # area code is 3 digits (e.g. '800')
        \D*         # optional separator is any number of non-digits
        (\d{3})     # trunk is 3 digits (e.g. '555')
        \D*         # optional separator
        (\d{4})     # rest of number is 4 digits (e.g. '1212')
        ''', re.VERBOSE)

    timePattern = re.compile(r'(([01]\d|2[0-3]):([0-5]\d)|24:00)', re.VERBOSE)

    endings = [u' ', u',', u'.', u'?', u'/', u')', u':']

    # Get Posts
    graph = facebook.GraphAPI(oauth_access_token)
    g = graph.get_connections("198031415602", "feed", limit=200)

    for post in g['data']:
        if post.has_key('message'):
            data = {}
            message = post['message']
            for word in [u"יוצא", u"מוזמנים", u"למהירי החלטה", u"למהרי החלטה", u"לספונטנים"]:
                if word in message:
                    data['status'] = "offering"
            for word in [u"מחפש", u"מישהו נוסע", u"מי נוסע", u"מישהו יוצא"]:
                if word in message:
                    data['status'] = "searching"

            with open('towns.csv', 'rb') as csvfile:
                spamreader = csv.reader(csvfile, delimiter=',', quotechar='|')

                for row in spamreader:
                    mainword = row[0]
                    words = [mainword]
                    if row[1] != "":
                        words = words+row[1].split(',')
                    for word in words:
                        word = unicode(word, 'utf-8')
                        
                        for start in [u"מ", u"מאזור ", u"מאיזור ", u'מכיוון ', u'מכוון ', u"מאיזור ", u"מצומת "]:
                            for end in endings:
                                if start+word+end in message:
                                    data['from'] = words[0]
                        for start in [u" ל", u" אל ", u"לקיבוץ ", u" עד ", u" לכיוון ", u" לכוון ", u" לכיון ", u"לצומת ", u"לאזור ", u"לאיוזר "]:
                            for end in endings:
                                if start+word+end in message:
                                    data['to'] = words[0]
            
            if phonePattern.search(message):
                n = phonePattern.search(message).group().replace("-", "")
                number = n[0:3]+"-"+n[3:6]+"-"+n[6:10]
                data['phone'] = number
            
            data['id'] = post['id']
            data['name'] = post['from']['name']
            data['userid'] = post['from']['id']
            data['date'] = arrow.get(post['created_time'])
            data['ridedate'] = arrow.get(post['created_time']).to('local')

            # understand when
            if u'מחר' in message:
                data['ridedate'] = data['ridedate'].replace(days=+1)
            elif u'עוד שעה' in message:
                data['ridedate'] = data['ridedate'].replace(hours=+1)
            elif u'עוד שעתיים' in message:
                data['ridedate'] = data['ridedate'].replace(hours=+2)
            else:

                days = {u'ראשון': 0,
                    u'שני': 1,
                    u'שלישי': 2,
                    u'רביעי': 3,
                    u'חמישי': 4,
                    u'שישי': 5,
                    u'שבת': 6}
                for day in days.keys():
                    for end in endings:
                        if day+end in message:
                            today = arrow.now().weekday()
                            difference = days[day] - today
                            
                            if difference >= 0:
                                data['ridedate'] = data['ridedate'].replace(days=+difference)
                            else:
                                data['ridedate'] = data['ridedate'].replace(days=+difference+7)
            
            for hour in range(1,24):
                for start in [u'סביבות ', u'ב', u'בשעה ', u'סביבות השעה ', u'סביבות שעה ']:
                    if start+str(hour) in message:
                        if data['date'] < data['ridedate'].replace(hour=hour):
                            data['ridedate'] = data['ridedate'].replace(hour=hour)
                        else:
                            if hour >= 12: ## todo next day?
                                data['ridedate'] = data['ridedate'].replace(hour=hour)
                            else:
                                data['ridedate'] = data['ridedate'].replace(hour=hour+12)

            if timePattern.search(message):
                data['ridedate'] = data['ridedate'].replace(hour=int(timePattern.search(message).group()[0:2]))
                data['ridedate'] = data['ridedate'].replace(minute=int(timePattern.search(message).group()[3:5]))

            data['message'] = message
            yesterday = arrow.now().replace(days=-1)


            if data['ridedate'] > yesterday:
                if data['ridedate'] == data['date']:
                    data['ridedate'] = None
                if data.has_key('status'):
                    if data['status'] == "searching":
                        searching.append(data)
                    else:
                        offering.append(data)
                else:
                    not_sure.append(data)

    return render_template('home.jade', searchings=searching, offerings=offering, not_sure=not_sure)

if __name__ == "__main__":
    app.run()
