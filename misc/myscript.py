from bs4 import BeautifulSoup
import re
import sys
sys.path.append('/Users/mplis15/personal/workspace/dlf-rankings-scrape')
import nfdl_keepers
sys.path.append('/Users/mplis15/personal/workspace/python-mfl/mfl')
import api as mfl_api
import csv
from sets import Set


def get_all_bids():
  league_year = 2015
  league_id = 70421
  api = mfl_api.Api(league_year)
  api.login(league_id, '0007', sys.argv[1])

  current_bids_page = api.opener.open('http://football.myfantasyleague.com/{}/options?L={}&O=43'.format(league_year, league_id))
  soup = BeautifulSoup(current_bids_page.read())
  auction_table = soup.find_all('table')[1]
  current_bids = auction_table.find_all('tr')[1:]

  finished_bids_page = api.opener.open('http://football.myfantasyleague.com/{}/options?L={}&O=102'.format(league_year, league_id))
  soup2 = BeautifulSoup(finished_bids_page.read())
  auction_table = soup2.find_all('table')[1]
  finished_bids = auction_table.find_all('tr')[1:]

  return (current_bids, finished_bids)

def extract_bids():
  bids = get_all_bids()
  current_bids = bids[0]
  finished_bids = bids[1]
  rankings = nfdl_keepers.dlf_rankings()
  bidding_opened_on = Set()
  with open('nasty26_auction2.csv', 'wb') as csvfile:
    writer = csv.writer(csvfile, delimiter = ',')
    x = ['Name', 'Salary', 'Owner', 'ADP', 'Rank', 'Age', 'Position', 'Bidding Order']
    writer.writerow(x)

    for i, bid in enumerate(current_bids):
      d = bid.find_all('td')
      player_info = re.split('[ ,]+', d[0].text.strip())
      salary = re.search('^(\$[\d,]+).*', d[1].text).group(1)
      owner = re.search("(.*) \(\$(.*)\)", d[2].text).group(1)
      if len(player_info) == 5 and player_info[4] != '(R)':
        last_name = ' '.join(player_info[0:2])
        first_name = player_info[2]
      elif player_info[0] != '*':
        last_name = player_info[0]
        first_name = player_info[1]
      else:
        first_name = ' '.join(player_info[2:5])
        last_name = ''
      key = nfdl_keepers.normalize_name('{}, {}'.format(last_name, first_name))
      bidding_opened_on.add(key)
      try:
        ranking = rankings[key]
        x = [ranking['player'], salary, owner, ranking['adp'], ranking['rank'], ranking['age'], ranking['position'], i]
        writer.writerow(x)
      except:
        x = ['{} {}'.format(first_name, last_name), salary, owner, '', '', '', '', i]
        writer.writerow(x)

    for bid in finished_bids:
      # mostly duplicate code from above; only difference is no bidding order
      d = bid.find_all('td')
      player_info = re.split('[ ,]+', d[0].text.strip())
      salary = re.search('^(\$[\d,]+).*', d[1].text).group(1)
      owner = re.search('(<font.*>)?([\w \.]+)(</font>)?', d[2].img['alt']).group(2)
      if len(player_info) == 5 and player_info[4] != '(R)':
        last_name = ' '.join(player_info[0:2])
        first_name = player_info[2]
      elif player_info[0] != '*':
        last_name = player_info[0]
        first_name = player_info[1]
      else:
        first_name = ' '.join(player_info[2:5])
        last_name = ''
      key = nfdl_keepers.normalize_name('{}, {}'.format(last_name, first_name))
      bidding_opened_on.add(key)
      try:
        ranking = rankings[key]
        x = [ranking['player'], salary, owner, ranking['adp'], ranking['rank'], ranking['age'], ranking['position'], '']
        writer.writerow(x)
      except:
        x = ['{} {}'.format(first_name, last_name), salary, owner, '', '', '', '', '']
        writer.writerow(x)


    for k, ranking in rankings.iteritems():
      if k not in bidding_opened_on:
        x = [ranking['player'], '', '', ranking['adp'], ranking['rank'], ranking['age'], ranking['position']]
        writer.writerow(x)

def get_rows(url, api):
  page = api.opener.open(url)
  soup = BeautifulSoup(page.read())
  return soup.find_all('table')[2].find_all('tr')[1:]

def rows_to_csv(rows, file_name):
  with open(file_name, 'wb') as csvfile:
    writer = csv.writer(csvfile, delimiter = ',')
    headers = ['Name', 'Salary', 'Owner', 'ADP', 'Rank', 'Age', 'Position']
    writer.writerow(headers)
    for row in rows:
      d = row.find_all('td')
      player_info = re.split('[ ,]+', d[0].text.strip())
      salary = re.search('^(\$[\d,]+).*', d[1].text).group(1)
      owner = re.search('(<font.*>)?([\w \.]+)(</font>)?', d[2].img['alt']).group(2)
      import pdb; pdb.set_trace()
      #if len(player_info) == 5 and player_info[4] != '(R)':
      if len(player_info) == 5:
        last_name = ' '.join(player_info[0:2])
        first_name = player_info[2]
      elif player_info[0] != '*':
        last_name = player_info[0]
        first_name = player_info[1]
      else:
        first_name = ' '.join(player_info[2:5])
        last_name = ''
      key = nfdl_keepers.normalize_name('{}, {}'.format(last_name, first_name))
      rankings = nfdl_keepers.dlf_rankings()
      try:
        ranking = rankings[key]
        x = [ranking['player'], salary, owner, ranking['adp'], ranking['rank'], ranking['age'], ranking['position']]
        writer.writerow(x)
      except:
        x = ['{} {}'.format(first_name, last_name), salary, owner, '', '', '', '']
        writer.writerow(x)

if __name__ == '__main__':
  extract_bids()





