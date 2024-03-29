# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

from __future__ import print_function

from itertools import chain

from portage.dep import use_reduce, extract_affecting_use, check_required_use, get_required_use_flags
from portage.output import colorize
from _emerge.DepPrioritySatisfiedRange import DepPrioritySatisfiedRange

class circular_dependency_handler(object):
	
	def __init__(self, depgraph, graph):
		self.depgraph = depgraph
		self.graph = graph
		self.all_parent_atoms = depgraph._dynamic_config._parent_atoms

		self.cycles, self.shortest_cycle = self._find_cycles()
		#Guess if it is a large cluster of cycles. This usually requires
		#a global USE change.
		self.large_cycle_count = len(self.cycles) > 3
		self.merge_list = self._prepare_reduced_merge_list()
		#The digraph dump
		self.circular_dep_message = self._prepare_circular_dep_message()
		#Suggestions, in machine and human readable form
		self.solutions, self.suggestions = self._find_suggestions()

	def _find_cycles(self):
		shortest_cycle = None
		cycles = self.graph.get_cycles(ignore_priority=DepPrioritySatisfiedRange.ignore_medium_soft)
		for cycle in cycles:
			if not shortest_cycle or len(cycle) < len(shortest_cycle):
				shortest_cycle = cycle
		return cycles, shortest_cycle

	def _prepare_reduced_merge_list(self):
		"""
		Create a merge to be displayed by depgraph.display().
		This merge list contains only packages involved in
		the circular deps.
		"""
		display_order = []
		tempgraph = self.graph.copy()
		while not tempgraph.empty():
			nodes = tempgraph.leaf_nodes()
			if not nodes:
				node = tempgraph.order[0]
			else:
				node = nodes[0]
			display_order.append(node)
			tempgraph.remove(node)
		display_order.reverse()
		return display_order

	def _prepare_circular_dep_message(self):
		"""
		Like digraph.debug_print(), but prints only the shortest cycle.
		"""
		if not self.shortest_cycle:
			return None

		msg = []
		indent = ""
		for pos, pkg in enumerate(self.shortest_cycle):
			parent = self.shortest_cycle[pos-1]
			priorities = self.graph.nodes[parent][0][pkg]
			if pos > 0:
				msg.append(indent + "%s (%s)" % (pkg, priorities[-1],))
			else:
				msg.append(indent + "%s depends on" % pkg)
			indent += " "

		pkg = self.shortest_cycle[0]
		parent = self.shortest_cycle[-1]
		priorities = self.graph.nodes[parent][0][pkg]
		msg.append(indent + "%s (%s)" % (pkg, priorities[-1],))

		return "\n".join(msg)

	def _get_use_mask_and_force(self, pkg):
		pkgsettings = self.depgraph._frozen_config.pkgsettings[pkg.root]
		pkgsettings.setcpv(pkg)
		return frozenset(pkgsettings.usemask), frozenset(pkgsettings.useforce)

	def _get_autounmask_changes(self, pkg):
		needed_use_config_change = self.depgraph._dynamic_config._needed_use_config_changes.get(pkg)
		if needed_use_config_change is None:
			return frozenset()

		use, changes = needed_use_config_change
		return frozenset(changes.keys())

	def _find_suggestions(self):
		if not self.shortest_cycle:
			return None, None

		suggestions = []
		final_solutions = {}

		for pos, pkg in enumerate(self.shortest_cycle):
			parent = self.shortest_cycle[pos-1]
			priorities = self.graph.nodes[parent][0][pkg]
			parent_atoms = self.all_parent_atoms.get(pkg)

			if priorities[-1].buildtime:
				dep = parent.metadata["DEPEND"]
			elif priorities[-1].runtime:
				dep = parent.metadata["RDEPEND"]

			for ppkg, atom in parent_atoms:
				if ppkg == parent:
					changed_parent = ppkg
					parent_atom = atom.unevaluated_atom
					break

			affecting_use = extract_affecting_use(dep, parent_atom)

			# Make sure we don't want to change a flag that is 
			#	a) in use.mask or use.force
			#	b) changed by autounmask
			
			usemask, useforce = self._get_use_mask_and_force(parent)
			autounmask_changes = self._get_autounmask_changes(parent)
			untouchable_flags = frozenset(chain(usemask, useforce, autounmask_changes))

			affecting_use.difference_update(untouchable_flags)

			#If any of the flags we're going to touch is in REQUIRED_USE, add all
			#other flags in REQUIRED_USE to affecting_use, to not lose any solution.
			required_use_flags = get_required_use_flags(parent.metadata["REQUIRED_USE"])

			if affecting_use.intersection(required_use_flags):
				affecting_use.update(required_use_flags)
				affecting_use.difference_update(untouchable_flags)

			affecting_use = tuple(affecting_use)

			if not affecting_use:
				continue

			#We iterate over all possible settings of these use flags and gather
			#a set of possible changes
			#TODO: Use the information encoded in REQUIRED_USE
			use_state = []
			for flag in affecting_use:
				use_state.append("disabled")

			def _next_use_state(state, id=None):
				if id is None:
					id = len(state)-1

				if id == 0 and state[0] == "enabled":
					return False

				if state[id] == "disabled":
					state[id] = "enabled"
					for i in range(id+1,len(state)):
						state[i] = "disabled"
					return True
				else:
					return _next_use_state(state, id-1)

			solutions = set()
			while(True):
				current_use = set(self.depgraph._pkg_use_enabled(parent))
				for flag, state in zip(affecting_use, use_state):
					if state == "enabled":
						current_use.add(flag)
					else:
						current_use.discard(flag)
				reduced_dep = use_reduce(dep,
					uselist=current_use, flat=True)

				if parent_atom not in reduced_dep:
					#We found an assignment that removes the atom from 'dep'.
					#Make sure it doesn't conflict with REQUIRED_USE.
					required_use = parent.metadata["REQUIRED_USE"]

					if check_required_use(required_use, current_use, parent.iuse.is_valid_flag):
						use = self.depgraph._pkg_use_enabled(parent)
						solution = set()
						for flag, state in zip(affecting_use, use_state):
							if state == "enabled" and \
								flag not in use:
								solution.add((flag, True))
							elif state == "disabled" and \
								flag in use:
								solution.add((flag, False))
						solutions.add(frozenset(solution))

				if not _next_use_state(use_state):
					break

			for solution in solutions:
				ignore_solution = False
				for other_solution in solutions:
					if solution is other_solution:
						continue
					if solution.issuperset(other_solution):
						ignore_solution = True
				if ignore_solution:
					continue

				#Check if a USE change conflicts with use requirements of the parents.
				#If a requiremnet is hard, ignore the suggestion.
				#If the requirment is conditional, warn the user that other changes might be needed.
				followup_change = False
				parent_parent_atoms = self.depgraph._dynamic_config._parent_atoms.get(changed_parent)
				for ppkg, atom in parent_parent_atoms:

					atom = atom.unevaluated_atom
					if not atom.use:
						continue

					for flag, state in solution:
						if flag in atom.use.enabled or flag in atom.use.disabled:
							ignore_solution = True
							break
						elif atom.use.conditional:
							for flags in atom.use.conditional.values():
								if flag in flags:
									followup_change = True
									break

					if ignore_solution:
						break

				if ignore_solution:
					continue

				changes = []
				for flag, state in solution:
					if state:
						changes.append(colorize("red", "+"+flag))
					else:
						changes.append(colorize("blue", "-"+flag))
				msg = "- %s (Change USE: %s)\n" \
					% (parent.cpv, " ".join(changes))
				if followup_change:
					msg += " (This change might require USE changes on parent packages.)"
				suggestions.append(msg)
				final_solutions.setdefault(pkg, set()).add(solution)

		return final_solutions, suggestions

	def debug_print(self):
		"""
		Create a copy of the digraph, prune all root nodes,
		and call the debug_print() method.
		"""
		graph = self.graph.copy()
		while True:
			root_nodes = graph.root_nodes(
				ignore_priority=DepPrioritySatisfiedRange.ignore_medium_soft)
			if not root_nodes:
				break
			graph.difference_update(root_nodes)

		graph.debug_print()
