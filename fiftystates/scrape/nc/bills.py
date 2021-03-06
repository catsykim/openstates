import datetime as dt
import re

import html5lib

from fiftystates.scrape.bills import BillScraper, Bill

class NCBillScraper(BillScraper):

    state = 'nc'
    soup_parser = html5lib.HTMLParser(
        tree=html5lib.treebuilders.getTreeBuilder('beautifulsoup')).parse

    def get_bill_info(self, session, bill_id):
        bill_detail_url = 'http://www.ncga.state.nc.us/gascripts/'\
            'BillLookUp/BillLookUp.pl?bPrintable=true'\
            '&Session=%s&BillID=%s&votesToView=all' % (
            session, bill_id)

        # parse the bill data page, finding the latest html text
        if bill_id[0] == 'H':
            chamber = 'lower'
        else:
            chamber = 'upper'

        bill_data = self.urlopen(bill_detail_url)
        bill_soup = self.soup_parser(bill_data)

        bill_title = bill_soup.findAll('div',
                                       style="text-align: center; font: bold"
                                       " 20px Arial; margin-top: 15px;"
                                       " margin-bottom: 8px;")[0].contents[0]

        bill = Bill(session, chamber, bill_id, bill_title)
        bill.add_source(bill_detail_url)

        # get all versions
        links = bill_soup.findAll('a', href=re.compile(
                '/Sessions/%s/Bills/\w+/HTML' % session[0:4]))

        for link in links:
            version_name = link.parent.previousSibling.previousSibling
            version_name = version_name.contents[0].replace('&nbsp;', ' ')
            version_name = version_name.replace(u'\u00a0', ' ')

            version_url = 'http://www.ncga.state.nc.us' + link['href']
            bill.add_version(version_name, version_url)

        # figure out which table has sponsor data
        sponsor_table = bill_soup.findAll('th', text='Sponsors',
                                          limit=1)[0].findParents(
            'table', limit=1)[0]

        sponsor_rows = sponsor_table.findAll('tr')
        for leg in sponsor_rows[1].td.findAll('a'):
            bill.add_sponsor('primary',
                             leg.contents[0].replace(u'\u00a0', ' '))
        for leg in sponsor_rows[2].td.findAll('a'):
            bill.add_sponsor('cosponsor',
                             leg.contents[0].replace(u'\u00a0', ' '))

        action_table = bill_soup.findAll('th', text='Chamber',
                                         limit=1)[0].findParents(
            'table', limit=1)[0]

        for row in action_table.findAll('tr'):
            cells = row.findAll('td')
            if len(cells) != 3:
                continue

            act_date, actor, action = map(lambda x: self.flatten(x), cells)
            act_date = dt.datetime.strptime(act_date, '%m/%d/%Y')

            if actor == 'Senate':
                actor = 'upper'
            elif actor == 'House':
                actor = 'lower'
            elif action.endswith('Gov.'):
                actor = 'Governor'

            bill.add_action(actor, action, act_date)

        self.save_bill(bill)

    def scrape(self, chamber, session):
        chamber = {'lower': 'House', 'upper': 'Senate'}[chamber]
        url = 'http://www.ncga.state.nc.us/gascripts/SimpleBillInquiry/'\
            'displaybills.pl?Session=%s&tab=Chamber&Chamber=%s' % (
            session, chamber)

        data = self.urlopen(url)
        soup = self.soup_parser(data)

        for row in soup.findAll('table')[6].findAll('tr')[1:]:
            td = row.find('td')
            bill_id = td.a.contents[0]
            self.get_bill_info(session, bill_id)

    def flatten(self, tree):

        def squish(tree):
            if tree.string:
                s = tree.string
            else:
                s = map(lambda x: self.flatten(x), tree.contents)
            if len(s) == 1:
                s = s[0]
            return s

        return ''.join(squish(tree)).strip()

