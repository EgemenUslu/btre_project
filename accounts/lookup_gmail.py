from __future__ import print_function
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from googleapiclient import errors
import string


from datetime import datetime
from dateutil import tz

from requests import exceptions as requests_errors

from google.auth.exceptions import RefreshError
from .social_auth_credentials import Credentials
from social_django.utils import load_strategy

from .models import JobApplication
import base64
import time

def removeHtmlTags(string):
    string = string.replace('\\r', '')
    string = string.replace('\\t', '')
    string = string.replace('\\n', '')
    string = string.replace('<br>', '')
    return string

def convertTime(base):

    # METHOD 2: Auto-detect zones:
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()

    # utc = datetime.utcnow()
    #utc = datetime.strptime('2011-01-21 02:37:21', '%Y-%m-%d %H:%M:%S')
    print(base)
    base = base[:25].strip()
    utc = datetime.strptime(base, '%a, %d %b %Y %H:%M:%S')
    #Mon, 1 Oct 2018 22:35:03 +0000 (UTC)

    # Tell the datetime object that it's in UTC time zone since
    # datetime objects are 'naive' by default
    utc = utc.replace(tzinfo=from_zone)

    # Convert time zone
    central = utc.astimezone(to_zone)
    return central.strftime('%Y-%m-%d')
    #return central.strftime('%a, %d %b %Y %H:%M:%S %z')

def find_nth(string, substring, n):
   if (n == 1):
       return string.find(substring)
   else:
       return string.find(substring, find_nth(string, substring, n - 1) + 1)

def GetMessage(service, user_id, msg_id, user, source):
  """Get a Message with given ID.
  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    msg_id: The ID of the Message required.
  Returns:
    A Message.
  """
  try:
    message = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()
    jobTitle = ''
    company = ''
    date = ''
    '''for part in message['payload']['parts']:
        if(part['mimeType'] == 'text/html'):
            print()
            print(base64.urlsafe_b64decode(part['body']['data'].encode('ASCII')))
            print()
            print()'''
    for header in message['payload']['headers']:
        if header['name'] == 'Subject':
            #print('Message subject: %s' % header['value'])
            subject = str(header['value'])
            if(source == 'LinkedIn'):
                jobTitle = subject[subject.index('for ') + 4 : subject.index(' at ')]
                company = subject[subject.index('at ') + 3:]
            elif(source == 'Hired.com'):
                jobTitle = subject[subject.index('st: ') + 4 : subject.index(' at ')]
                company = subject[subject.index('at ') + 3 : subject.index('(')]
            elif(source == 'Indeed'):
                jobTitle = subject[subject.index('Indeed Application: ') + 20 : ]
        elif header['name'] == 'Date':
            date = header['value']
            date = convertTime(str(date))

    for part in message['payload']['parts']:
        if(part['mimeType'] == 'text/html'):
            body = str(base64.urlsafe_b64decode(part['body']['data'].encode('ASCII')))
            s = find_nth(body, 'https://media.licdn.com', 2)
            if(s != -1):
                e = find_nth(body, '" alt="' + company + '"', 1)
                image_url = body[s : e].replace('&amp;', '&')
                print(image_url)
            else:
                image_url = 'https://d31kswug2i6wp2.cloudfront.net/images/3_0/icon_company_no-logo_200x200.jpg'
            if(source == 'Vettery'):
                jobTitle = body[body.index('Role: ') + 6 : body.index('Salary')]
                jobTitle = removeHtmlTags(jobTitle)
                company = body[body.index('interview with ') + 15 : body.index('. Interested?')]
            elif(source == 'Indeed'):
                company = body[body.index('Get job updates from <b>') + 24 : body.index('</b>.<br><i>By selecting')]

    if user.is_authenticated:
      inserted_before = JobApplication.objects.all().filter(msgId=msg_id)
      if not inserted_before:
        japp = JobApplication(jobTitle=jobTitle, company=company, applyDate=date, msgId=msg_id, source = source, user = user, companyLogo = image_url)
        japp.save()


    ja = JobApplication(jobTitle, company, date)
    return ja
  except errors.HttpError as error:
    print('An error occurred: %s' % error)



def ListMessagesMatchingQuery(service, user_id, query=''):
  """List all Messages of the user's mailbox matching the query.
  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    query: String used to filter messages returned.
    Eg.- 'from:user@some_domain.com' for Messages from a particular sender.
  Returns:
    List of Messages that match the criteria of the query. Note that the
    returned list contains Message IDs, you must use get with the
    appropriate ID to get the details of a Message.
  """
  try:
    response = service.users().messages().list(userId=user_id,
                                               q=query, includeSpamTrash=True).execute()
    messages = []
    if 'messages' in response:
      messages.extend(response['messages'])

    while 'nextPageToken' in response:
      page_token = response['nextPageToken']
      response = service.users().messages().list(userId=user_id, q=query,
                                         pageToken=page_token, includeSpamTrash=True).execute()
      messages.extend(response['messages'])

    return messages
  except errors.HttpError as error:
    print('An error occurred: %s' % error)

def fetchJobApplications(user):
    #initiates Gmail API
    usa = user.social_auth.get(provider='google-oauth2')
    GMAIL = build('gmail', 'v1', credentials=Credentials(usa))

    #print(str(time.gmtime()))
    linkedInMessages = ListMessagesMatchingQuery(GMAIL, 'me', 'from:jobs-listings@linkedin.com AND subject:You applied for')# AND after:2018/01/01')
    hiredMessages = ListMessagesMatchingQuery(GMAIL, 'me', 'from:reply@hired.com AND subject:Interview Request')
    vetteryMessages = ListMessagesMatchingQuery(GMAIL, 'me', 'from:@connect.vettery.com AND subject:Interview Request')
    indeedMessages = ListMessagesMatchingQuery(GMAIL, 'me', 'from:indeedapply@indeed.com AND subject:Indeed Application')
    #print('there is ' + str(len(messages)) + ' messages sent from jobs-listings@linkedin.com')

    for message in linkedInMessages:
        GetMessage(GMAIL, 'me', message['id'], user, 'LinkedIn')
    for message in hiredMessages:
        GetMessage(GMAIL, 'me', message['id'], user, 'Hired.com')
    for message in vetteryMessages:
        GetMessage(GMAIL, 'me', message['id'], user, 'Vettery')
    for message in indeedMessages:
        GetMessage(GMAIL, 'me', message['id'], user, 'Indeed')
