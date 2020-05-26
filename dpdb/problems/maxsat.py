# -*- coding: future_fstrings -*-
import logging
from collections import defaultdict

from dpdb.problem import *
from dpdb.reader import AdvancedCnfReader
from .sat_util import *

logger = logging.getLogger(__name__)

class MaxSat(Problem):

    def __init__(self, name, pool, store_formula=False, **kwargs):
        super().__init__(name, pool, **kwargs)
        self.store_formula = store_formula

    def td_node_column_def(self,var):
        return td_node_column_def(var)

    def td_node_extra_columns(self, node):
        return [("card","INTEGER")]

    def candidate_extra_cols(self,node):
        card = [node2card(n) for n in node.children]

        # add cardinalities for vars which will be removed in the parent node
        for v in node.vertices:
            if v not in node.stored_vertices or node.is_root():
                card.append(var2card(node, v, self.var_soft_clause_dict))

        card_q = " + ".join(card)

        card_q += " AS card"

        return [card_q]


    def assignment_extra_cols(self,node):
        return ["max(card) AS card"]

    def filter(self,node):
        return filter(self.var_hard_clause_dict, node)

    def setup_extra(self):
        def create_tables():
            self.db.ignore_next_praefix()
            self.db.create_table("problem_maxsat", [
                ("id", "INTEGER NOT NULL PRIMARY KEY REFERENCES PROBLEM(id)"),
                ("num_vars", "INTEGER NOT NULL"),
                ("num_clauses", "INTEGER NOT NULL"),
                ("max_sat_clauses", "NUMERIC"),
                ("is_sat", "BOOLEAN")
            ])

        def insert_data():
            self.db.ignore_next_praefix()
            self.db.insert("problem_maxsat",("id","num_vars","num_clauses"),
                (self.id, self.num_vars, self.num_clauses))
            if "faster" not in self.kwargs or not self.kwargs["faster"]:
                self.db.ignore_next_praefix()
                self.db.insert("problem_option",("id", "name", "value"),(self.id,"store_formula",self.store_formula))
                if self.store_formula:
                    store_clause_table(self.db, self.clauses)

        create_tables()
        insert_data()

    def prepare_input(self, fname):
        input = AdvancedCnfReader.from_file(fname)
        self.num_vars = input.num_vars
        self.num_clauses = input.num_clauses
        self.hard_clauses = input.hard_clauses
        self.soft_clauses = input.soft_clauses

        self.var_hard_clause_dict = defaultdict(set)
        self.var_soft_clause_dict = defaultdict(set)

        a,edges_hard = cnf2primal(input.num_vars, input.hard_clauses, self.var_hard_clause_dict)
        b,edges_soft = cnf2primal(input.num_vars, input.soft_clauses, self.var_soft_clause_dict)

        return (input.num_vars, edges_hard | edges_soft)

    def after_solve(self):
        root_tab = f"td_node_{self.td.root.id}"
        card_sql = self.db.replace_dynamic_tabs(f"(select coalesce(max(card),0) from {root_tab})")
        is_sat = self.db.replace_dynamic_tabs(f"(select exists(select 1 from {root_tab} WHERE card + {card_sql} = {len(self.hard_clauses) + len(self.soft_clauses)}))")
        self.db.ignore_next_praefix()
        sat = self.db.update("problem_maxsat",["is_sat"],[is_sat],[f"ID = {self.id}"],"is_sat")[0]
        self.db.ignore_next_praefix()
        max_clauses = self.db.update("problem_maxsat",["max_sat_clauses"],[card_sql],[f"ID = {self.id}"],"max_sat_clauses")[0]
        logger.info("Problem is %s", "SAT" if sat else "UNSAT")
        logger.info("Max satisfied clauses: %d", max_clauses)

def var2card(node,var,clauses):
    vertice_set = set(node.vertices)
    removed_vertices = [v for v in node.vertices if v not in node.stored_vertices or node.is_root()]
    removed_vertices.remove(var)
    cur_cl = set()
    candidates = clauses[var]
    for d in candidates:
        for key, val in d.items():
            if key.issubset(vertice_set) and \
                    (all(var <= v for v in key) or all(v not in key for v in removed_vertices)):
                cur_cl.add(val)

    if len(cur_cl) > 0:
        return " + ".join(
            ["case when {} then 1 else 0 end".format(
                " OR ".join(var2tab_col(node,lit,False) if lit > 0 else "not "+ var2tab_col(node,abs(lit),False) for lit in clause))
        for clause in cur_cl])
    else:
        return "0"


def node2card(node):
    return "{}.card".format(node2tab_alias(node))

args.specific[MaxSat] = dict(
    help="Solve MaxSAT instances",
    options={
        "--store-formula": dict(
            dest="store_formula",
            help="Store formula in database",
            action="store_true",
        ),
        "--soft-clauses": dict(
            dest="soft_clauses",
            help="Input file with explicit soft-clauses for the problem"
        )
    }
)
