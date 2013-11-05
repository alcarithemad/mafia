import math
import thread
import time

from collections import defaultdict

from roles import Roles, determine_roles

class MafiaGame(object):

	def __init__(self, irc, prefix, lock=None, round=0, pending=None):
		self.irc = irc
		self.prefix = prefix
		self.channels = {
			'town':'#'+prefix+'town',
			'mafia':'#'+prefix+'mafia',
		}
		for channel in self.channels.values():
			print 'joining', channel
			self.irc.join(channel)
			self.irc.mode(channel, '-m')
		self.irc.mode(self.channels['mafia'], '+si')
		# FIXME: self.irc.names is return None
		# for nick in self.irc.names([self.channels['mafia']]):
		# 	self.irc.kick(self.channels['mafia'], nick, 'clearing channel for game')
		self.pending = pending or set()
		self.players = {}
		self.time = 'day'
		self.date = 0
		self.round = 0
		self.phase_started = 0
		self.phase_lock = lock or thread.allocate_lock()
		self.vigilante_targets = {}
		self.investigate_targets = {}

	@property
	def in_progress(self):
		return not (self.time == 'day' and self.date == 0)

	def init_votes(self):
		# clear active vote marks and reset counters
		for player in self.players.values():
			player.active = defaultdict(lambda:False)

		self.votes = {
			'kill':defaultdict(lambda:0),
			'lynch':defaultdict(lambda:0),
		}
		self.voters = {
			'kill':len([p for p in self.players.values() if p.TEAM == 'mafia']),
			'lynch':len(self.players)
		}
		self.majorities = {}
		for kind, num in self.voters.items():
			print kind, num, int(math.ceil(num/2.0)), len(self.players)
			self.majorities[kind] = int(math.ceil(num/2.0+0.5))

	def add_player(self, name, role):
		self.players[name] = role(name, self)
		return self.players[name]

	def remove_player(self, name):
		p = self.players[name]
		self.irc.privmsg(self.channels['town'], '{}, {}, has been killed.'.format(name, p.TROLE))
		for kind, target in p.active.items():
			if target:
				self.votes[kind][target] -= 1
		del self.players[name]

	def start_game(self):
		self.irc.privmsg(self.channels['town'], 'Starting game. Assigning roles...')
		roles = determine_roles(len(self.pending))
		print roles
		for player, role in zip(self.pending, roles):
			print player
			self.players[player] = role(player, self)
			self.irc.privmsg(player, "Your role is: {}.".format(role.ROLE))
			self.irc.privmsg(player, role.DESC)
		self.init_votes()
		thread.start_new_thread(self.phase_countdown, ())
		self.start_day()

	def check_victory(self):
		if not any(p for p in self.players.values() if p.TEAM == 'mafia'):
			self.irc.privmsg(self.channels['town'], 'All the mafia members are dead! The citizens win.')
		elif len([p for p in self.players.values() if p.TEAM == 'mafia']) > len([p for p in self.players.values() if p.TEAM == 'town']):
			self.irc.privmsg(self.channels['town'], 'The mafia outnumbers the honest citizens! The mafia wins.')
		elif len(self.players) == 2:
			self.irc.privmsg(self.channels['town'], 'Only a single citizen remains. The mafia wins.')
		else:
			return False

		return True

	def phase_countdown(self):
		date_time = self.date, self.time, self.round
		self.phase_started = time.time()
		print 'asdf'
		for x in xrange(3):
			if (self.date, self.time, self.round) == date_time:
				time_left = 'There are {} minutes left in the {}.'.format(5-x, self.time)
				self.irc.privmsg(self.channels['town'], time_left)
				self.irc.privmsg(self.channels['mafia'], time_left)
				time.sleep(60)
		if (self.date, self.time, self.round) == date_time:	
			time_left = 'There is 1 minute left in the {}.'.format(self.time)
			self.irc.privmsg(self.channels['town'], time_left)
			self.irc.privmsg(self.channels['mafia'], time_left)
			time.sleep(60)
		if (self.date, self.time, self.round) == date_time:
			locked = self.phase_lock.acquire(0)
			if locked:
				msg = 'Time ran out with no majority vote.'
				self.irc.privmsg(self.channels['town'], msg)
				self.irc.privmsg(self.channels['mafia'], msg)
				self.next_phase()
				self.phase_lock.release()


	def next_phase(self):
		over = self.check_victory()
		if over:
			self.__init__(self.irc,
				self.prefix,
				lock=self.phase_lock,
				round=self.round+1,
				pending=self.pending,
			)
			return
		self.init_votes()
		thread.start_new_thread(self.phase_countdown, ())
		if self.time == 'day':
			self.start_night()
		elif self.time == 'night':
			self.start_day()

	def start_night(self):
		self.time = 'night'
		self.irc.privmsg(self.channels['town'], 'Night has fallen.')
		self.irc.privmsg(self.channels['mafia'], 'It is now night. Killing requires {} votes.'.format(self.majorities['kill']))
		self.night_actions = sum(p.NIGHT_ACTIONS for p in self.players.values())
		for player in self.players.values():
			player.skip = False
		self.irc.mode(self.channels['town'], '+m')
		self.irc.mode(self.channels['mafia'], '-m')

	def start_day(self):
		self.time = 'day'
		self.date += 1
		self.irc.privmsg(self.channels['town'], 'It is now morning. Lynching requires {} votes.'.format(self.majorities['lynch']))
		for vigilante, target in self.vigilante_targets:
			if vigilante in self.players:
				self.remove_player(target)
		for cop, target in self.investigate_targets:
			if cop in self.players:
				result = self.players[target].INNOCENT
				if self.players[cop].INSANE:
					result = not result
				result = 'innocent' if result else 'guilty'
				self.irc.privmsg(cop, 'Your investigation finds {} to be {}.'.format(target, result))
		self.vigilante_targets = {}
		self.investigate_targets = {}
		self.irc.mode(self.channels['town'], '-m')
		self.irc.mode(self.channels['mafia'], '+m')

	def vote(self, kind, player, dest, target):
		if player.active[kind]:
			old = player.active[kind]
			self.votes[kind][old] -= 1
		if target in self.players:
			player.active[kind] = target
			self.votes[kind][target] += 1
		else:
			player.active[kind] = None
			self.irc.privmsg(dest, '{} cleared their vote.'.format(player.name))
		majority = math.ceil(self.majorities[kind])
		print majority, self.votes[kind]
		for player, votes in self.votes[kind].items():
			if votes >= majority:
				locked = self.phase_lock.acquire(0)
				if locked:
					self.remove_player(player)
					self.phase_lock.release()
				self.next_phase()
				break

	def kill(self, player, dest, target):
		if self.time == 'night':
			self.vote('kill', player, dest, target)
			self.irc.privmsg(self.channels['mafia'], '{} has voted to !kill {}'.format(player.name, target))
		else:
			self.irc.privmsg(player.name, "Can't vote to kill now.")
			pass

	def lynch(self, player, dest, target):
		if self.time == 'day':
			self.irc.privmsg(self.channels['town'], '{} has voted to !lynch {}'.format(player.name, target))
			self.vote('lynch', player, dest, target)
		else:
			self.irc.privmsg(player.name, "Can't vote to lynch now.")
			pass

	def vigilante_kill(self, player, dest, target):
		# TODO: confirm with player
		self.irc.privmsg(player.name, 'You will kill {} by daybreak, or die trying.'.format(target))
		self.vigilante_targets[player.name] = target

	def investigate(self, player, dest, target):
		self.investigate_targets[player.name] = target

	def status(self, player, dest, *a):
		status = "It's currently {0} {1}. There are {2} living players.".format(
				self.time, self.date, len(self.players), 
			) 
		if self.phase_started:
			status += " There are {0} seconds left in the {1}.".format(int(300-(time.time()-self.phase_started)), self.time)
		self.irc.privmsg(dest, status)

	def skip(self, player, dest):
		self.irc.privmsg(player.name, 'You will skip your night actions.')
		if not player.skip:
			player.skip = True
			self.night_actions -= 1
		if self.night_actions == 0:
			self.next_phase()

	def handle(self, info, dest, a):
		nick = info.source.nick
		player = self.players.get(nick)
		sp = a[0].lstrip('!').split()
		cmd = sp[0]
		args = sp[1:]
		print 'handling', player or nick, cmd, 'args', args
		if cmd == 'join':
			self.pending.add(nick)
			self.irc.privmsg(dest, "{} will be in the next round.".format(nick))
		elif cmd == 'help':
			self.irc.privmsg(nick, 'help message not implemented >_>')
		elif cmd == 'start':
			if self.in_progress:
				self.irc.privmsg(nick, "There's already a game in progress.")
			if len(self.pending) < 1:
				self.irc.privmsg(dest, "Not enough players to !start.")
			else:
				self.start_game()

		if player:
			if self.time == 'day':
				cmd = player.day.get(cmd)
			elif self.time == 'night':
				cmd =  player.night.get(cmd)

			if cmd:
				try:
					cmd(player, dest, *args)
				except:
					self.irc.privmsg(dest, 'Not enough parameters given!')

if __name__ == '__main__':
	print Roles.keys()
	game = MafiaGame()
	alice = game.add_player('alice', Roles['Citizen'])
	bob = game.add_player('bob', Roles['Citizen'])
	carol = game.add_player('carol', Roles['Citizen'])
	dave = game.add_player('dave', Roles['Citizen'])
	eve = game.add_player('eve', Roles['Mafia'])
	game.lynch(alice, 'bob')
	game.lynch(carol, 'bob')
	game.lynch(eve, 'bob')
	game.kill(eve, 'alice')
	print game.players.keys(), game.time, game.date
