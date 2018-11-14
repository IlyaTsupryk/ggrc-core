# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""  Fast digest handlers """
import itertools

from werkzeug import exceptions
from google.appengine.api import mail

from ggrc import db
from ggrc import rbac
from ggrc import settings

from ggrc.notifications.proposal_helpers import build_prosal_data
from ggrc.notifications.proposal_helpers import get_email_proposal_list
from ggrc.notifications.proposal_helpers import mark_proposals_sent
from ggrc.notifications.review_helpers import build_review_data
from ggrc.notifications.review_helpers import get_review_notifications
from ggrc.notifications import common

DIGEST_TITLE = "Proposal Digest"
DIGEST_TMPL = settings.JINJA2.get_template("notifications/fast_digest.html")


def build_address_body(proposals, review_notifications):
  """yields email address and email body"""
  proposal_dict = build_prosal_data(proposals)
  review_dict = build_review_data(review_notifications)
  people = set(
      itertools.chain(
          proposal_dict.iterkeys(),
          review_dict["reviewers_data"].iterkeys(),
          review_dict["owners_data"].iterkeys()
      )
  )
  for addressee in people:
    review_reviewers_data = review_dict["reviewers_data"][addressee]
    review_owners_data = review_dict["owners_data"][addressee]
    proposals = proposal_dict[addressee]
    body = DIGEST_TMPL.render(
        proposals=proposals.values(),
        review_reviewers=review_reviewers_data.values(),
        review_owners=review_owners_data.values(),
    )
    yield (addressee, body)


def send_notification():
  """Send notifications about proposals."""
  proposals = get_email_proposal_list()
  review_notifications = get_review_notifications()
  for addressee, html in build_address_body(proposals,
                                            review_notifications):
    mail.send_mail(
        sender=getattr(settings, "APPENGINE_EMAIL"),
        to=addressee.email,
        subject=DIGEST_TITLE,
        body="",
        html=html,
    )
  mark_proposals_sent(proposals)
  common.move_notifications_to_history(review_notifications)
  db.session.commit()


def present_notifications():
  """Present fast digest notifications."""
  if not rbac.permissions.is_admin():
    raise exceptions.Forbidden()
  proposals = get_email_proposal_list()
  review_notifications = get_review_notifications()
  generator = (
      u"<h1> email to {}</h1>\n {}".format(addressee.email, body)
      for addressee, body in build_address_body(proposals,
                                                review_notifications)
  )
  return u"".join(generator)
