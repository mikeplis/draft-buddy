from flask import Flask, render_template, jsonify, request, make_response
import urllib
import urllib2
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import datetime
from itertools import groupby
import json
import re

app = Flask(__name__)
mfl_url = 'http://football.myfantasyleague.com'
year = 2015
league_id = 70421
franchise_id = '0007'
auction_budget = 400.0
num_teams = 12
roster_size = 28

@app.template_filter('pct')
def pct(s):
  return s * 100

@app.template_filter('dollar')
def dollar(s):
  return '$ {}'.format(s)

@app.route('/')
def home():
  return render_template('home.html')

@app.route('/current_bids')
def current_bids():
  # user could give these values as input on home page, then store them in cookie
  password = request.args.get('password')
  (opener, session_id) = mfl_login(year, league_id, franchise_id, password)
  bids = get_bids(opener, year, league_id, current_only=True)
  resp = make_response(render_template('current_bids.html', bids=bids))
  if session_id is not None:
    resp.set_cookie('mfl_session_id', session_id)
  return resp

@app.route('/position-grid')
def position_grid():
  password = request.args.get('password')
  (opener, session_id) = mfl_login(year, league_id, franchise_id, password)
  bids = get_bids(opener, year, league_id)

  sorted_bids = sorted(bids, key=lambda b: b['high_bidder'])
  rows = []
  totals = {'owner': 'Total', 'RB': 0, 'WR': 0, 'QB': 0, 'TE': 0}
  total_spent = 0
  for owner, owner_bids in groupby(sorted_bids, lambda b: b['high_bidder']):
    owner_bids = list(owner_bids)
    row = { 'owner': owner, 'RB': 0, 'WR': 0, 'QB': 0, 'TE': 0 }
    spent = 0
    for owner_bid in owner_bids:
      bid_amount = owner_bid['high_bid']
      row[owner_bid['position']] += bid_amount
      totals[owner_bid['position']] += bid_amount
      spent += bid_amount
      total_spent += bid_amount
    row['RB_pct'] = row['RB'] / auction_budget
    row['WR_pct'] = row['WR'] / auction_budget
    row['QB_pct'] = row['QB'] / auction_budget
    row['TE_pct'] = row['TE'] / auction_budget
    row['left'] = auction_budget - spent
    row['left_pct'] = row['left'] / auction_budget
    row['per_player_spent'] = spent / len(owner_bids)
    row['per_player_left'] = (auction_budget - spent) / (roster_size - len(owner_bids))
    rows.append(row)
  totals['RB_pct'] = totals['RB'] / (auction_budget * num_teams)
  totals['WR_pct'] = totals['WR'] / (auction_budget * num_teams)
  totals['QB_pct'] = totals['QB'] / (auction_budget * num_teams)
  totals['TE_pct'] = totals['TE'] / (auction_budget * num_teams)
  totals['left'] = (auction_budget * num_teams) - totals['RB'] - totals['WR'] - totals['QB'] - totals['TE']
  totals['left_pct'] = totals['left'] / (auction_budget * num_teams)
  totals['per_player_spent'] = total_spent / len(bids)
  totals['per_player_left'] = (auction_budget * num_teams - total_spent) / ((roster_size * num_teams) - len(bids))
  rows.append(totals)

  resp = make_response(render_template('position-grid.html', rows=rows, json_rows=json.dumps(rows)))
  if session_id is not None:
    resp.set_cookie('mfl_session_id', session_id)
  return resp

@app.route('/against-adp')
def against_adp():
  password = request.args.get('password')
  (opener, session_id) = mfl_login(year, league_id, franchise_id, password)
  rows = get_bids(opener, year, league_id)

  adp = get_adp()
  for row in rows:
    key = ' '.join(row['player'].replace(' ', '').replace('.', '').split(',')[::-1])
    row['adp'] = adp.get(key)

    hours, remainder = divmod(row['over_in'].seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    row['over_in_str'] = '{} hours, {} minutes'.format(hours, minutes)
    # convert to hours to determine size of point in chart
    row['size'] = ((row['over_in'].seconds / 3600) + 1) ** -1 if not row['is_over'] else 16 ** -1

    # unused keys fail serialization
    row.pop('started', None)
    row.pop('last_bid', None)
    row.pop('over_in', None)
    

  resp = make_response(render_template('against-adp.html', rows=rows, json_rows=json.dumps(rows)))
  if session_id is not None:
    resp.set_cookie('mfl_session_id', session_id)
  return resp

def bids_to_dict(bids):
  d = {}
  for bid in bids:
    d[bid['key']] = bid
  return d

@app.route('/all-adp')
def all_adp():
  password = request.args.get('password')
  (opener, session_id) = mfl_login(year, league_id, franchise_id, password)
  bids = get_bids(opener, year, league_id)
  bids_dict = bids_to_dict(bids)
  rows = []

  adps = get_adp()
  for player, adp in adps.iteritems():
    row = {}
    row['player'] = player
    row['adp'] = adp
    if player in bids_dict:
      bid = bids_dict[player]
      row['team'] = bid['team']
      row['position'] = bid['position']
      row['bid'] = bid['high_bid']
      row['status'] = 'Finished' if bid['is_over'] else 'Ongoing'
    else:
      row['team'] = ''
      row['position'] = ''
      row['bid'] = ''
      row['status'] = 'Not started'
    rows.append(row)

  resp = make_response(render_template('all-adp.html', rows=rows, json_rows=json.dumps(rows)))
  if session_id is not None:
    resp.set_cookie('mfl_session_id', session_id)
  return resp

def get_adp():
  opener = urllib2.build_opener()
  opener.addheaders = [('User-agent', 'Mozilla/5.0')]
  url = 'http://dynastyleaguefootball.com/adpdata/2015-adp/?month=4'
  soup = BeautifulSoup(opener.open(url).read())
  rows = soup.find_all('table')[0].find_all('tr')[1:]
  adps = {}
  for row in rows:
    td = row.find_all('td')
    player = td[2].a.text
    if player == 'Odell Beckham Jr.':
      player = 'Odell Beckham'
    if player == 'Devante Parker':
      player = 'DeVante Parker'
    adps[player] = float(td[4].text)
  return adps

def mfl_strptime(s):
  return datetime.datetime.strptime(s.replace('.', ''), '%a %b %d %I:%M:%S %p ET %Y')

def get_bids(opener, year, league_id, current_only=False):
  (curr_bids, fin_bids) = get_bids_from_mfl(opener, year, league_id)
  bids_html = curr_bids if current_only else curr_bids + fin_bids
  bid_list = []
  for i, bid_html in enumerate(bids_html):
    bid = {}
    d = bid_html.find_all('td')
    player_info = d[0].text.replace('(R)', '').strip().rsplit(' ', 2)
    bid['player'] = player_info[0]
    bid['team'] = player_info[1]
    bid['position'] = player_info[2]
    bid_amount = float(d[1].text.rsplit(' ',1)[0].replace('$', ''))
    bid['high_bid'] = bid_amount
    bid['pct_budget'] = bid_amount / auction_budget
    bid['high_bidder'] = re.search('([\w@ !]+ ?[\w!]+)( \(\$\d+)?', d[2].text).group(1)
    bid['started'] = mfl_strptime(d[3].text)
    bid['last_bid'] = mfl_strptime(d[4].text)
    bid['over_in'] = (bid['last_bid'] + datetime.timedelta(hours=16)) - datetime.datetime.now()
    bid['is_over'] = bid['over_in'].total_seconds() < 0
    key = ' '.join(bid['player'].replace(' ', '').replace('.', '').split(',')[::-1])
    bid['key'] = key
    bid_list.append(bid)
  return bid_list

def get_bids_from_mfl(opener, year, league_id):
  current_bids_url = '{}/{}/options?L={}&O=43'.format(mfl_url, year, league_id)
  soup = BeautifulSoup(opener.open(current_bids_url).read()) 
  current_bids = soup.find_all('table')[1].find_all('tr')[1:]

  finished_bids_url = '{}/{}/options?L={}&O=102'.format(mfl_url, year, league_id)
  soup = BeautifulSoup(opener.open(finished_bids_url).read()) 
  finished_bids = soup.find_all('table')[1].find_all('tr')[1:]
  
  return (current_bids, finished_bids)

def mfl_login(year, league_id, franchise_id, password):
  params = urllib.urlencode({
            'L': league_id,
            'FRANCHISE_ID': franchise_id,
            'PASSWORD': password,
            'XML': 1})
  mfl_login_url = '{}/{}/login'.format(mfl_url, year)
  url = '{}?{}'.format(mfl_login_url, params)
  opener = urllib2.build_opener()
  if request.cookies.get('mfl_session_id') is None:
    resp = urllib2.urlopen(url)
    session_id = ET.fromstring(resp.read()).attrib['session_id']  
    opener.addheaders.append(('Cookie', 'USER_ID={}'.format(session_id)))
    return (opener, session_id)
  else:
    opener.addheaders.append(('Cookie', 'USER_ID={}'.format(request.cookies.get('mfl_session_id'))))
    return (opener, None)

if __name__ == '__main__':
    app.run(debug=True)
