# Amara, universalsubtitles.org
#
# Copyright (C) 2012 Participatory Culture Foundation
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see
# http://www.gnu.org/licenses/agpl-3.0.html.
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.views.generic.list_detail import object_list

from auth.models import CustomUser as User
from teams.models import Team, TeamMember
from videos.models import Video, Action

from mock import patch, Mock

class TestViews(TestCase):
    fixtures = ['test.json']

    def _simple_test(self, url_name, args=None, kwargs=None, status=200, data={}):
        response = self.client.get(reverse(url_name, args=args, kwargs=kwargs), data)
        self.assertEqual(response.status_code, status)
        return response

    def _login(self):
        self.client.login(**self.auth)

    def _prepare_team(self, team, members=[], visibility=None):
        TeamMember.objects.all().delete()
        map(lambda member:TeamMember.objects.create(team=team, user=member), members)
        if visibility != None:
            team.is_visible = visibility
            team.save()
            
    def setUp(self):
        self.auth = dict(username='admin', password='admin')
        self.user = User.objects.get(username=self.auth['username'])

    def test_edit_account(self):
        self._simple_test('profiles:account', status=302)

        self._login()
        self._simple_test('profiles:account')

        data = {
            'username': 'new_username_for_admin',
            'email': self.user.email,
            'userlanguage_set-TOTAL_FORMS': '0',
            'userlanguage_set-INITIAL_FORMS': '0',
            'userlanguage_set-MAX_NUM_FORMS': ''
        }
        response = self.client.post(reverse('profiles:account'), data=data)
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(pk=self.user.pk)
        self.assertEqual(user.username, data['username'])

        other_user = User.objects.exclude(pk=self.user.pk)[:1].get()
        data['username'] = other_user.username
        response = self.client.post(reverse('profiles:account'), data=data)
        self.assertEqual(response.status_code, 200)

    def test_edit_profile(self):
        self._simple_test('profiles:edit', status=302)

        self._login()
        self._simple_test('profiles:edit')

        data = {
            'username': 'new_username_for_admin',
            'email': 'someone@example.com',
            'userlanguage_set-TOTAL_FORMS': '0',
            'userlanguage_set-INITIAL_FORMS': '0',
            'userlanguage_set-MAX_NUM_FORMS': ''
        }
        response = self.client.post(reverse('profiles:edit'), data=data)
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(pk=self.user.pk)
        # the view sets this from the user model, make sure are not
        # able to change this
        self.assertNotEqual(user.username, data['username'])
        self.assertNotEqual(user.email, data['email'])
        other_user = User.objects.exclude(pk=self.user.pk)[:1].get()
        data['username'] = other_user.username
        response = self.client.post(reverse('profiles:edit'), data=data)
        self.assertRedirects(response, reverse('profiles:edit'))

    def test_profile_page(self):
        video = Video.objects.all()[0]
        video.title = 'new title'
        video.save()
        Action.change_title_handler(video, self.user)
        self.assertTrue(self.user.action_set.exists())

        self._simple_test('profiles:profile', [self.user.id])
    
    def test_team_visibility(self):
        team = Team.objects.all()[0]
        user = self.user
        other_user = User.objects.exclude(pk=self.user.pk)[:1].get()
        self._login()

        with patch('profiles.views.object_list', new=Mock(wraps=object_list)) as mock:
            # private teams of others are not visible to us when we are non team members
            self._prepare_team(team, members=[other_user], visibility=False)
            self.client.get(reverse('profiles:profile', args=(other_user.id,)))
            self.assertEqual(len(mock.call_args[1]['extra_context']['teams']), 0)

            # public teams of others are visible us non members
            self._prepare_team(team, members=[other_user], visibility=True)
            self.client.get(reverse('profiles:profile', args=(other_user.id,)))
            self.assertEqual(len(mock.call_args[1]['extra_context']['teams']), 1)
            self.assertEqual(mock.call_args[1]['extra_context']['teams'][0], team)

            # private teams of others are visible to us if we are also team members
            self._prepare_team(team, members=[user, other_user], visibility=False)
            self.client.get(reverse('profiles:profile', args=(other_user.id,)))
            self.assertEqual(len(mock.call_args[1]['extra_context']['teams']), 1)
            self.assertEqual(mock.call_args[1]['extra_context']['teams'][0], team)

            # if viewing own profile, then 'teams' context var not required
            # The template falls back to displaying user.teams.all()
            self._prepare_team(team, members=[user])
            self.client.get(reverse('profiles:profile', args=(user.id,)))
            self.assertNotIn('teams', mock.call_args[1]['extra_context'])
