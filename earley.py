from __future__ import annotations
from typing import List, Tuple
import itertools
import json

#Earley Parser Implementation
NT = 'NON_TERMINAL'
T = 'TERMINAL'
NIL = 'NIL'  # Both the EOF and the type of EOF

def get_symbol_type(symbol):
    if symbol == NIL:
        return NIL
    if symbol.islower():
        return T
    if symbol.isupper():
        return NT
    raise Exception("Invalid symbol")

class Rule:
    '''
    A rule is of the form A->[l...]
    where A is a non-terminal and [l...] is a 
    list of terminals + non-terminals.
    '''

    def __init__(self, name, productions):
        self.name = name
        self.productions = productions

    def __str__(self):
        prods_str = ' '.join(self.productions)
        return f'{self.name} -> {prods_str}'
    
    def __repr__(self):
        return self.__str__()


class Grammar:
    def __init__(self, rules):
        self.rules = rules


class Item(Rule):
    '''
    An Earley Item consists of a Grammar Rule, a dot position, start and end.
    
    The start and end correspond to the range of the input sentence
    that has been successfully parsed.

    The symbols that come on the left side of the dot represent
    all symbols of the rule that have been successfully parsed as
    the tokens (within the input range).

    For example, the item A -> dB @ E (start=3, end=6)   (@ is the dot)
    parsing the string abcdefg means
    
    The substring def has been parsed as dB, in the hopes of getting to the rule A -> dBE.
    '''

    def __init__(self, name, productions, dot, start, end, histories = [[]]):
        super().__init__(name, productions)
        self.dot = dot
        self.start = start
        self.end = end
        self.histories = histories

    @property
    def next(self) -> str:
        if self.dot == len(self.productions):
            return NIL        
        next_symbol = self.productions[self.dot]
        return next_symbol
    
    @property
    def concise_repr(self):
        prods = ' '.join(self.productions)
        return f'{self.name} -> {prods} [{self.start}-{self.end}]'
    
    def copy(self):
        return Item(self.name, self.productions, self.dot, self.start, self.end, self.histories)

    @classmethod
    def from_rule(cls, rule: Rule, dot: int, start: int, end: int):
        return cls(rule.name, rule.productions, dot, start, end)
    
    def __str__(self):
        front = self.productions[:self.dot]
        back = self.productions[self.dot:]
        big = front + ['@'] + back
        prods_str = ' '.join(big)
        return f'{self.name} -> {prods_str} ({self.start}-{self.end}) {self.histories}'
    
    def __repr__(self):
        return self.__str__()
    
    def __eq__(self, other):
        return self.name == other.name and \
        self.productions == other.productions and \
        self.dot == other.dot and \
        self.start == other.start


class Node:
    '''
    N-ary tree Node. For building back the parse tree at the end
    '''

    def __init__(self, children: List[Node], uid:int, payload:Item):
        self.children = children
        self.uid = uid
        self.payload = payload

    def json(self):
        return {self.payload.concise_repr:[q.json() for q in self.children]}

    def __str__(self):
        if self.children:
            child_str = ',\n'.join(['\n   '.join(x.__str__().split('\n')) for x in self.children])
            child_str = f'(\n{child_str}\n)'
        else:
            child_str = '()'
        return f'{self.uid}{child_str}'
    
    def __repr__(self):
        return self.__str__()


class MultiNode:
    '''
    N-ary tree node with multiple choice points for its children.
    For building up the parse forest (different ways of making the parse tree)
    at the end.
    '''

    def __init__(self, children: List[List[MultiNode]], uid: int, payload:Item):
        self.children = children
        self.uid = uid
        self.payload = payload
    
    def multidfs(self) -> List[Node]:
        result = []
        for choice_group in self.children:
            list_of_trees: List[List[Node]] = []
            for child in choice_group:
                child_trees: List[Node] = child.multidfs()
                list_of_trees.append(child_trees)

            all_possibilities: List[List[Node]] = \
                [p for p in itertools.product(*list_of_trees)]
            
            all_trees_per_cp: List[Node] = \
                [Node(possible_combination, self.uid, self.payload) 
                 for possible_combination in all_possibilities]
            result.extend(all_trees_per_cp)
        return result
    

def pretty_print_s(state_list):
    for i in range(len(state_list)):
        print('')
        print(f'---------- Level {i}')
        for j in range(len(state_list[i])):
            print(f'{j}: {state_list[i][j]}')

class EarleyParser:
    '''
    Main parsing logic. Parsing works by generating a state table which
    represents the set of all items that can be obtained.
     
    We start with only one item in the table: a special "start" item.
    
    Now, for every item in the table, we apply one of the following actions 
    (depending on the item's form): either a PREDICTION, SCAN or COMPLETION
    action, if possible. These actions add new items to the table, so we run 
    the actions on the new items again.
     
    We repeat this process until there are no more new actions that can be taken.

    A final item is defined as any item with a start and end spanning the
    entire sentence, and with the dot at the end.

    We collate all the final items, and apply depth-first search back through 
    the table to pick up all the other items that contributed to a successful parse.

    The way we keep track of this is through keeping a history log whenever
    we perform the COMPLETION action.

    This algorithm was taken from the code at the end of this article 
    https://loup-vaillant.fr/tutorials/earley-parsing/recogniser 

    The history graph action was eyeballed (inferred) from this set of slides
    https://www.inf.ed.ac.uk/teaching/courses/inf2a/slides2017/inf2a_L21_slides.pdf

    How we keep track multiple histories was an inductive leap of faith
    that I just took without any thought to it. I'm not sure if it is correct.

    I'm sure there's a way to formally prove it. But I'm quite lazy.    
    '''

    def __init__(self, grammar, privileged_pos):
        self.grammar: List[Rule] = grammar
        self.privileged_pos: List[str] = privileged_pos
    
    def generate_state_table(self, start_rule: Rule, sentence: List[str], step_through: False):
        # print(sentence, len(sentence))
        # print("sentence length", len(sentence) + 1)
        state_table: List[List[Item]] = [[] for i in range(len(sentence) + 1)]
        state_table[0].append(Item.from_rule(start_rule, 0, 0, 0))


        for i in range(len(sentence) + 1):
            print("")
            print("============")
            print(f"Looping through items in layer {i}")
            j = 0
            while j < len(state_table[i]):

                if step_through:
                    _ = input()
                    print('')
                    print('================= NEW STEP =================')
                    pretty_print_s(state_table)                    

                item =  state_table[i][j]
                next_type = get_symbol_type(item.next)

                # Run prediction step
                if next_type == NT:
                    for rule in self.grammar.rules:
                        if (rule.name == item.next):
                            new_item = Item.from_rule(rule, 0, i, i)

                            # Short-circuit the predict step for privileged POS
                            # if the word does not correspond to input
                            if new_item.name in privileged_pos: 
                                target_word = new_item.productions[0]
                                if(sentence[i] != target_word):
                                    continue

                            print(f"Prediction on {item}, generates {new_item} in slot {i}")
                            if new_item not in state_table[i]: # dont track duplicates
                                state_table[i].append(new_item)

                # Run scan step
                elif next_type == T: #scan
                    if sentence[i] == item.next:
                        new_item = item.copy()
                        new_item.dot += 1
                        new_item.end = i+1
                        print(f"Scan on {item}, generates {new_item} in slot {i+1}")
                        if new_item not in state_table[i]: # dont track duplicates
                            state_table[i+1].append(new_item)

                # Run complete step
                elif next_type == NIL: 
                    prev_i = item.start
                    for prev_item in state_table[prev_i]:
                        if prev_item.next == item.name:

                            new_item = prev_item.copy()
                            new_item.dot += 1
                            new_item.end = i
                            # Append the current item (the trigger) to the history
                            new_item.histories = [q + [(i, j)] for q in prev_item.histories]

                            print(f"Completion on {item}, generates {new_item} in slot {i}")
                            if new_item not in state_table[i]:
                                state_table[i].append(new_item)
                            else:
                                # I AM NOT SURE IF THIS IS CORRECT!!!
                                # If we generate a duplicate item in COMPLETION, 
                                # we update the existing item in the table,
                                # by adding the new history as new "choice points".
                                # my guess is that this will allow us to get all choice points.

                                # i suppose this is equivalent to just not de-duplicating
                                # during a complete step, and do normal DFS on the graph.

                                # actually now that i think about it. That would probably have been
                                # easier to implement.
                                seen_item = [l for l in state_table[i] if l == new_item][0]
                                seen_item.histories.extend(new_item.histories)

                else:
                    raise Exception("Invalid symbol type!")
                
                j += 1

        return state_table

    def parse(self, start_rule, sentence, step_through=False):

        print('')
        print('Generating state table for sentence' + ' '.join(sentence) + '...')

        states = self.generate_state_table(start_rule, sentence, step_through)

        pretty_print_s(states)

        # Convert the state table into a table of nodes
        states_as_nodes: List[List[MultiNode]] = [[]]
        for lvl_idx, level in enumerate(states):
            for item in level:
                states_as_nodes[lvl_idx].append(
                    MultiNode([], (item.concise_repr), item))
            states_as_nodes.append([])
        
        for level in states_as_nodes:
            for node_item in level:
                for history in node_item.payload.histories:
                    new_history = []
                    for i, j in history:
                        new_history.append(states_as_nodes[i][j])
                    node_item.children.append(new_history)


        # Get final states
        final_states = [i for i in states_as_nodes[len(sentence)-1] if i.payload.start == 0]
        if len(final_states) == 0:
            raise Exception("Invalid Parse!")
        print('')

        # Loop through all states and perform DFS with choice points
        all_outputs = []
        for fstates in final_states:
            trees = fstates.multidfs()
            for tree in trees:
                q = tree.json()
                output = json.dumps(q, indent=4)
                all_outputs.append(output)
                print('')

        unique_outputs = set(all_outputs)
        
        # Print the resulting trees
        print('Final parse trees:')
        for o in unique_outputs:
            print(o)
            print('')



S = 'S'
NP = 'NP'
N = 'N'
PP = 'PP'
VP = 'VP'
V = 'V'
P = 'P'

grammar  = Grammar(
    [
        Rule(S, [NP, VP]),
        Rule(NP, [N, PP]),
        Rule(NP, [N]),
        Rule(PP, [P, NP]),
        Rule(VP, [VP, PP]),
        Rule(VP, [V, VP]),
        Rule(VP, [V, NP]),
        Rule(VP, [V]),

        Rule(N, ['they']),
        Rule(N, ['fish']),
        Rule(N, ['can']),
        Rule(N, ['rivers']),
        Rule(N, ['december']),

        Rule(P, ['in']),

        Rule(V, ['can']),
        Rule(V, ['fish']),
    ]
)

print("The 'toy' grammar rules:")
for rule in grammar.rules:
    print(rule)

start_rule = Rule(S, [NP, VP])
privileged_pos = [N, P, V] # Parts of Speech
# sentence = ['they', 'can', 'fish', 'in', 'rivers', 'EOF']
sentence = ['they', 'can', 'fish', 'in', 'rivers', 'in', 'december', 'EOF']
parser = EarleyParser(grammar, privileged_pos)
# try:
parser.parse(start_rule, sentence, False)
# except:
#     pass
# print(final_state)
# def dfs(node):
#     print(node)
#     for history in node.histories:
#         for i, j in history:
#             dfs(states[i][j])

# print("Final parse tree:")
# dfs(final_state)
# parser.parse(start_rule, sentence)

# mylist = [1, 2]
# j = 0
# while j < len(mylist):
#     print(mylist[j])
#     mylist.append(j)