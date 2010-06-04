from mw_greylist.glcandidate import GLCandidate
from mw_greylist.glentry import GLEntry
from mw_greylist.settings import Settings
from mw_greylist.pluginframework import ActionProvider
from mw_greylist.exceptions import *
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os.path
import sys
import unittest
from datetime import datetime, timedelta
#import mw_greylist.core.exceptions

class mw_greylistTest(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()
        self.settings.connection_url = 'sqlite:///:memory:'
        engine = create_engine(self.settings.connection_url)
        GLEntry.metadata.create_all(engine)
        Session.configure(bind=engine)
        self.session = Session()
        self.glc = GLCandidate(self.settings, self.session)
        self.glc.plugins = ActionProvider.plugins
        script_path = sys.argv[0]
        script_path = os.path.split(script_path)[0]
        self.header_file = script_path + "/header_file.txt"

    def testReadHeadersFromExistingFile(self):
        self.glc.read_headers(self.header_file)
        self.assertEqual('1.2.3.4',
                         self.glc.headers['client_address'])

    def testInvalidHeaderLine(self):
        self.failUnlessRaises(GLHeaderException, 
                              self.glc._split_headers, 
                              'foo')

    def testValidHeaderLine(self):
        self.assertEqual(['name', 'value'], 
                         self.glc._split_headers('name=value\n'))

    def testMultipleEqualSignHeaderLine(self):
        self.assertEqual(['name', 'value==value'],
                         self.glc._split_headers('name=value==value\n'))
                         
    def testEmptyHeaderLine(self):
        self.assertEqual(None,
                         self.glc._split_headers('\n'))

    def testHeaderFromFileLineCount(self):
        fh = open(self.header_file)
        lines = fh.readlines()
        self.glc.read_headers(self.header_file)
        self.assertEqual(len(lines),
                         len(self.glc.headers))

    def testHeaderAddedCorrectly(self):
        self.glc.read_headers(self.header_file)
        self.assertEqual(self.glc.headers['client_address'], '1.2.3.4')

    def testActionShouldReturnTestForInvalidEntry(self):
        entry = GLEntry(client='1.2.3.4', helo='some.domain.tld', sender='bar.tld')
        self.session.add(entry)
        self.session.commit()
        self.glc.read_headers(self.header_file)
        self.assertEqual('TEST', self.glc.get_action())
    
    def testActionShouldReturnAllowForCurrentWL(self):
        entry = GLEntry(client='1.2.3.4', helo='some.domain.tld', sender='bar.tld')
        entry.status = 'W'
        entry.expiry_date = datetime.now() + timedelta(hours=1)
        self.session.add(entry)
        self.session.commit()
        self.glc.read_headers(self.header_file)
        self.assertEqual('ALLOW', self.glc.get_action())

    def testPerformActionShouldReturnDunnoForExpiredGL(self):
        entry = GLEntry(client='1.2.3.4', helo='some.domain.tld', sender='bar.tld')
        entry.status = 'G'
        entry.expiry_date = datetime.now() - timedelta(minutes=5)
        self.session.add(entry)
        self.session.commit()
        self.glc.read_headers(self.header_file)
        self.assertEqual('DUNNO\n\n', self.glc.perform_action())
        self.assertEqual(None, self.glc.score)

    def testPerformActionShouldReturn450ForActiveGL(self):
        entry = GLEntry(client='1.2.3.4', helo='some.domain.tld', sender='bar.tld')
        entry.status = 'G'
        entry.expiry_date = datetime.now() + timedelta(minutes=5)
        self.session.add(entry)
        self.session.commit()
        self.glc.read_headers(self.header_file)
        self.assertEqual(self.glc.settings.greylist_message, self.glc.perform_action())
        self.assertEqual(None, self.glc.score)

    def testPerformActionShouldWriteScoreForInactiveWL(self):
        entry = GLEntry(client='1.2.3.4', helo='some.domain.tld', sender='bar.tld')
        entry.status = 'W'
        entry.expiry_date = datetime.now() - timedelta(minutes=5)
        self.session.add(entry)
        self.session.commit()
        self.glc.read_headers(self.header_file)
        self.glc.perform_action()
        self.assertNotEqual(None, self.glc.score)

if __name__ == '__main__':
    Session = sessionmaker()
    unittest.main()
