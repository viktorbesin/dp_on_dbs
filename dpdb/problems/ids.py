# -*- coding: future_fstrings -*-
import logging

from dpdb.reader import TdReader, TwReader, EdgeReader
from dpdb.problem import *

logger = logging.getLogger(__name__)

class IndependentDominatingSet(Problem, Countable):

    def __init__(self, name, pool, input_format, **kwargs):
        self.input_format = input_format
        super().__init__(name, pool, **kwargs)

    def td_node_column_def(self,var):
        return (var2col(var), "BOOLEAN")

    def td_node_extra_columns(self, node):
        return [(var2col_dominance(v), "BOOLEAN") for v in node.vertices] +  [("size","INTEGER")]
        
    def candidate_extra_cols(self,node):
        dominations = [var2dominance(node,v,self.edges[v]) + " AS " + var2col_dominance(v)
                          for v in node.vertices]

        size = [node2size(n) for n in node.children]

        # add sizes for vertices which will be removed in the parent node
        for v in node.vertices:
            if v not in node.stored_vertices or node.is_root():
                size.append(var2size(node, v))

        size_q = " + ".join(size)

        if size:
            size_q += " AS size"
        else:
            size_q = "0 AS size"

        return dominations + [size_q]

    def assignment_extra_cols(self,node):
        return [var2col_dominance(v) if v in node.stored_vertices
                else f"null::BOOLEAN " + var2col_dominance(v) for v in node.vertices] + ["min(size) AS size"]

    def filter(self, node):
        dominations = [var2col_dominance(v)for v in node.vertices if v not in node.stored_vertices or node.is_root()]

        independence = []
        edges = []

        for c in node.vertices:
            [edges.append((c,v)) for v in self.edges[c] if v in node.vertices and (v,c) not in edges]

        for edge in edges:
            independence.append("not ({} AND {})".format(var2col(edge[0]), var2col(edge[1])))

        if dominations:
            if independence:
                return "WHERE ({})".format(") AND (".join(dominations+independence))
            else:
                return "WHERE ({})".format(") AND (".join(dominations))
        else:
            if independence:
                return "WHERE ({})".format(") AND (".join(independence))
            else:
                return ""



    def setup_extra(self):
        def create_tables():
            self.db.ignore_next_praefix()
            self.db.create_table("problem_ids", [
                ("id", "INTEGER NOT NULL PRIMARY KEY REFERENCES PROBLEM(id)"),
                ("size", "INTEGER")
            ])

        def insert_data():
            self.db.ignore_next_praefix(1)
            self.db.insert("problem_ids",("id",),(self.id,))

        create_tables()
        insert_data()

    def prepare_input(self, fname):
        if self.input_format == "td":
            input = TdReader.from_file(fname)
        elif self.input_format == "tw":
            input = TwReader.from_file(fname)
        elif self.input_format == "edge":
            input = EdgeReader.from_file(fname)
        self.num_vertices = input.num_vertices
        self.edges = input.adjacency_list

        return (input.num_vertices, input.edges)

    def after_solve(self):
        root_tab = f"td_node_{self.td.root.id}"
        size_sql = self.db.replace_dynamic_tabs(f"(select coalesce(min(size),0) from {root_tab})")
        self.db.ignore_next_praefix()
        self.size = self.db.update("problem_ids",["size"],[size_sql],[f"ID = {self.id}"],"size")[0]
        logger.info("Min independent dominating set size: %d", self.size)

    def group_extra_cols(self,node):
        return [var2col_dominance(v) for v in node.stored_vertices]

    # Overwriting Countable
    def c_after_solve_select(self):
        return (["sum(count)"], [f"size = {self.size}"])

    def c_after_solve_log(self, count):
        logger.info("Problem has %d interpretations with minIDS %d", count, self.size)

    def c_extra_cols(self):
        return ["size"]

    def c_extra_cols_comparison(self):
        return ["min(size)"]

    def c_filter_problem(self, node):
        return self.filter(node)


def var2size(node,var):
    return "case when {} then 1 else 0 end".format(var2tab_col(node,var,False))


def node2size(node):
    return "{}.size".format(node2tab_alias(node))

def var2col_dominance(var):
    return f"d{var}"

# For Dominance:
# When Introduction needed: set to 1 when neighbor or self is set
# else: additional use dominance of child
def var2dominance(node, var, edges):
    # use iX.val if new variable, else child table dX
    if node.needs_introduce(var):
        child_dom = var2tab_col(node,var,False)
    else:
        child_dom = "{}.{}".format(var2tab_alias(node,var), var2col_dominance(var))

    neigh = []

    for v in edges:
        if v in node.vertices:
            neigh.append(var2tab_col(node,v,False))

    if neigh:
        return "case when {} then true else false end".format(" OR ".join(neigh + [child_dom]))
    else:
        return "case when {} then true else false end".format(child_dom)

args.specific[IndependentDominatingSet] = dict(
    help="Solve independent dominating set instances (min IDS)",
    aliases=["ids"],
    options={
        "--input-format": dict(
            dest="input_format",
            help="Input format",
            choices=["td","tw","edge"],
            default="td"
        )
    }
)

