import random

from collections import defaultdict

Roles = {}

class Role(type):

	def __new__(mcs, name, bases, dct):
		role = type.__new__(mcs, name, bases, dct)
		Roles[name] = role
		return role

class Player(object):
	__metaclass__ = Role
	ROLE = 'undefined'
	TEAM = 'town'
	CHANNELS = ['town']
	INNOCENT = True
	NIGHT_ACTIONS = 0

	def __init__(self, name, game):
		self.name = name
		self.game = game
		self.TROLE = self.ROLE
		self.active = defaultdict(lambda:False)
		self.day = {
			'lynch':game.lynch,
			'status':game.status,
		}
		if self.NIGHT_ACTIONS:
			self.night = {
				'skip':game.skip,
			}
		else:
			self.night = {}
		self.skip = False

class Citizen(Player):
	ROLE = 'citizen'
	DESC = 'During the day, citizens vote to !lynch one player, whom they suspect of being in the mafia. They sleep at night.'

class Cop(Citizen):
	ROLE = 'cop'
	DESC = 'The cop can !investigate one player each night, determining if they are innocent (a citizen) or guilty (a mafiosi).'
	NIGHT_ACTIONS = 1
	INSANE = False

	def __init__(self, name, game):
		super(Cop, self).__init__(name, game)
		self.night['investigate'] = game.investigate

class InsaneCop(Citizen):
	ROLE = 'cop'
	DESC = 'The cop can !investigate one player each night, determining if they are innocent (a citizen) or guilty (a mafiosi).'
	NIGHT_ACTIONS = 1
	INSANE = True

	def __init__(self, name, game):
		super(InsaneCop, self).__init__(name, game)
		self.TROLE = 'insane cop'

class Vigilante(Citizen):
	ROLE = 'vigilante'
	DESC = 'The vigilante can !kill one player each night with vigilante justice (also known as a Colt .44).'
	NIGHT_ACTIONS = 1

	def __init__(self, name, game):
		super(Vigilante, self).__init__(name, game)
		self.night['kill'] = game.vigilante_kill

class Mafia(Player):
	ROLE = 'mafia'
	TEAM = 'mafia'
	DESC = 'During the day, the mafia pretend to be honest citizens, but at night they vote to !kill one player.'
	CHANNELS = ['town', 'mafia']
	INNOCENT = False
	NIGHT_ACTIONS = 1

	def __init__(self, name, game):
		super(Mafia, self).__init__(name, game)
		self.night['kill'] = game.kill
		game.irc.invite(name, game.channels['mafia'])

class Godfather(Mafia):
	ROLE = 'godfather'
	DESC = 'Leader of the mafia, the godfather appears to be innocent when !investigated.'
	INNOCENT = True

random.seed()

def determine_roles(num_players):
	mafia = int(round(num_players/3.0))
	print mafia
	innocents = num_players - mafia
	ret = []
	if random.random() >= 0.5 and mafia > 0:
		ret.append(Roles['Godfather'])
		mafia -= 1
	if random.random() >= 0.75 and innocents > 0:
		if random.random() >= 0.98:
			ret.append(Roles['InsaneCop'])
		else:
			ret.append(Roles['Cop'])
		innocents -= 1
	if random.random() <= 0.05*innocents and innocents > 0:
		ret.append(Roles['Vigilante'])
		innocents -= 1
	ret += [Roles['Mafia']]*mafia
	ret += [Roles['Citizen']]*innocents
	random.shuffle(ret)
	return ret

if __name__ == '__main__':
	print determine_roles(5)
	print determine_roles(6)
	print determine_roles(8)