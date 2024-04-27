#Earley Parser Implementation

from typing import List, Tuple
from copy import deepcopy

# Both the EOF and the type of EOF
NT = 'NON_TERMINAL'
T = 'TERMINAL'
NIL = 'NIL' 

class Rule:
    def __init__(self, name, productions):
        self.name = name
        self.productions = productions

    def __str__(self):
        front = self.productions[:self.dot]
        back = self.productions[self.dot:]
        big = front + ['@'] + back
        prods_str = ' '.join(big)
        return f'{self.name} -> {prods_str}'
    
    def __repr__(self):
        return self.__str__()

class Grammar:
    def __init__(self, rules):
        self.rules = rules


def get_symbol_type(symbol):
    if symbol == NIL:
        return NIL
    if symbol.islower():
        return T
    if symbol.isupper():
        return NT
    raise Exception("Invalid symbol")

class Item(Rule):
    def __init__(self, name, productions, dot, start, histories = []):
        super().__init__(name, productions)
        self.dot = dot
        self.start = start
        self.histories = histories

    @property
    def next(self) -> str:
        if self.dot == len(self.productions):
            return NIL        
        next_symbol = self.productions[self.dot]
        return next_symbol
    
    def copy(self):
        return Item(self.name, self.productions, self.dot, self.start)

    @classmethod
    def from_rule(cls, rule, dot, start):
        return cls(rule.name, rule.productions, dot, start)
    
    def __str__(self):
        # print(self.dot, self.productions)
        front = self.productions[:self.dot]
        back = self.productions[self.dot:]
        big = front + ['@'] + back
        prods_str = ' '.join(big)
        return f'{self.name} -> {prods_str} ({self.start}) {self.histories}'
    
    def __repr__(self):
        return self.__str__()
    
    def __eq__(self, other):
        return self.name == other.name and \
        self.productions == other.productions and \
        self.dot == other.dot and \
        self.productions == other.productions and \
        self.start == other.start


def pretty_print_s(state_list):
    for i in range(len(state_list)):
        print('')
        print(f'---------- Level {i}')
        for j in range(len(state_list[i])):
            print(f'{j}: {state_list[i][j]}')

class EarleyParser:

    def __init__(self, grammar):
        self.grammar: List[Rule] = grammar
    
    def generate_state_table(self, start_rule: Rule, sentence: List[str]):

        state_table: List[List[Item]] = [[] for i in range(len(sentence) + 1)]
        state_table[0].append(Item.from_rule(start_rule, 0, 0))


        for i in range(len(sentence) + 1):
            print("")
            print("============")
            print(f"Looping through items in layer {i}")
            j = 0
            while j < len(state_table[i]):
                item =  state_table[i][j]
                next_type = get_symbol_type(item.next)

                # Run prediction step
                if next_type == NT:
                    for rule in self.grammar.rules:
                        if (rule.name == item.next):
                            new_item = Item.from_rule(rule, 0, i)

                            # Short-circuit the predict step for privileged POS
                            # if the word does not correspond to input
                            if new_item.name in privileged_pos: 
                                target_word = new_item.productions[0]
                                if(sentence[i] != target_word):
                                    continue

                            print(f"Prediction on {item}, generates {new_item} in slot {i}")
                            if new_item not in state_table[i]:
                                state_table[i].append(new_item)

                # Run scan step
                elif next_type == T: #scan
                    if sentence[i] == item.next:
                        new_item = item.copy()
                        new_item.dot += 1
                        print(f"Scan on {item}, generates {new_item} in slot {i+1}")
                        if new_item not in state_table[i]:
                            state_table[i+1].append(new_item)

                # Run complete step
                elif next_type == NIL: 
                    prev_i = item.start
                    for prev_item in state_table[prev_i]:
                        if prev_item.next == item.name:

                            new_item = prev_item.copy()
                            new_item.dot += 1
                            # Append the current item (the trigger) to the history
                            new_item.histories = prev_item.histories + [(i, j)] 

                            print(f"Completion on {item}, generates {new_item} in slot {i}")
                            if new_item not in state_table[i]:
                                state_table[i].append(new_item)

                else:
                    raise Exception("Invalid symbol type!")
                
                j += 1

            # self.pretty_print_s()
        # return state_table
        return state_table
    
    def parse(self, start_rule, sentence):
        states = self.generate_state_table(start_rule, sentence)

        print("Final states")
        pretty_print_s(states)

        final_states = [i for i in states[len(sentence)-1] if i.start == 0]
        if len(final_states) == 0:
            raise Exception("There is no final state!")

        final_state = final_states[0]
        def dfs(node):
            print(node)
            for i, j in node.histories:
                dfs(states[i][j])

        print("Final parse tree:")
        dfs(final_state)


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

        Rule(P, ['in']),

        Rule(V, ['can']),
        Rule(V, ['fish']),
    ]
)
start_rule = Rule(S, [NP, VP])
privileged_pos = [N, P, V] # Parts of Speech

sentence = ['they', 'can', 'fish', 'in', 'rivers', 'EOF']

parser = EarleyParser(grammar)
parser.parse(start_rule, sentence)
