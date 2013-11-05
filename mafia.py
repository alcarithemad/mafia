import math

from collections import defaultdict

from roles import Roles, determine_roles

class MafiaGame(object):

	def __init__(self, irc, prefix):
		self.irc = irc
		self.prefix = prefix
		self.channels = {
			'town':'#'+prefix+'town',
			'mafia':'#'+prefix+'mafia',
		}
		for channel in self.channels.values():
			print 'joining', channel
			self.irc.join(channel)
		self.pending = set()
		self.players = {}
		self.time = 'day'
		self.date = 0
		self.vigilante_targets = {}
		self.init_votes()

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
			self.majorities[kind] = int(math.ceil(num/2))

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
		self.start_day()

	def check_victory(self):
		if not any(p for p in self.players if p.TEAM == 'mafia'):
			self.irc.privmsg(self.channels['town'], 'All the mafia members are dead!')
		elif sum(p for p in self.players if p.TEAM == 'mafia') > sum(p for p in self.players if p.TEAM == 'town'):
			self.irc.privmsg(self.channels['town'], 'The mafia outnumbers the honest citizens!')
		else:
			return False

		self.irc.privmsg(self.channels['town'], 'The citizens win!')
		return True

	def next_phase(self):
		over = self.check_victory()
		if over:
			self.__init__(self.irc, self.prefix)
			return
		self.init_votes()
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
		# TODO: -m #town, +m #mafia

	def start_day(self):
		self.time = 'day'
		self.date += 1
		self.irc.privmsg(self.channels['town'], 'It is now morning. Lynching requires {} votes.'.format(self.majorities['lynch']))
		for vigilante, target in self.vigilante_targets:
			if vigilante in self.players:
				self.remove_player(target)
		self.vigilante_targets = {}

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
		majority = math.ceil(self.majorities[kind]/2)
		print majority, self.votes[kind]
		for player, votes in self.votes[kind].items():
			if votes >= majority:
				self.remove_player(player)
				self.next_phase()
				break

	def kill(self, player, dest, target):
		if self.time == 'night':
			self.vote('kill', player, dest, target)
			self.irc.privmsg(self.channels['town'], '{} has voted to !kill {}'.format(player.name, target))
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
		self.vigilante_target = target

	def investigate(self, player, dest, target):
		# TODO: implement me
		pass

	def insane_investigate(self, player, dest, target):
		# TODO: implement me
		pass

	def status(self, player, dest, target):
		self.irc.privmsg(dest, "It's currently {0} {1}. There are {2} living players.".format(self.time, self.date, len(self.players)))
		# TODO: list active players, time remaining, etc.

	def skip(self, player, dest, target):
		self.irc.privmsg(player.name, 'You will skip your night actions.')
		if not player.skip:
			player.skip = True
			self.night_actions -= 1

	def handle(self, info, dest, a):
		nick = info.source.nick
		player = self.players.get(nick)
		sp = a[0].lstrip('!').split()
		cmd = sp[0]
		args = sp[1:]
		print 'handling', player, cmd, 'args', args
		if not player:
			if cmd == 'join':
				self.pending.add(nick)
				self.irc.privmsg(nick, "You will be in the next round.")
			elif cmd == 'help':
				self.irc.privmsg(nick, 'help message not implemented >_>')
			elif cmd == 'start':
				if self.in_progress:
					self.irc.privmsg(nick, "There's already a game in progress.")
				if len(self.pending) < 1:
					self.irc.privmsg(dest, "Not enough players to !start.")
				else:
					self.start_game()
			return

		if self.time == 'day':
			cmd = player.day.get(cmd)
		elif self.time == 'night':
			cmd =  player.night.get(cmd)

		if cmd:
			cmd(player, dest, *args)

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
