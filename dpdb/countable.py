# -*- coding: future_fstrings -*-

class Countable(object):
    # overwrite the following methods (if required)

    # Some problems need the comparison of extra columns in the candidates to count correctly. return them here
    def c_extra_cols(self):
        return []

    # If a column needs to be compared, which value (from the candidates) should it be compared to? - respective order of extra_clauses_cols()
    def c_extra_cols_comparison(self):
        return []

    # Change the where to whatever is looked for
    def c_after_solve_select(self):
        return (["coalesce(sum(count),0)"], None)

    # Log the number of solutions
    def c_after_solve_log(self, count):
        pass

    # Filter the second candidate select, typically the node filter is needed here
    def c_filter_problem(self, node):
        return ""

    # the following methods can be overwritten at your own risk
    def count_col(self):
        return [("count","NUMERIC")]

    def count_assignment(self):
        return ["sum(count) AS count"]

    def count_candidate_cols(self,node):
        return ["{} AS count".format(
            " * ".join(set([var2cnt(node,v) for v in node.vertices] +
                           [node2cnt(n) for n in node.children])) if node.vertices or node.children else "1"
        )]

    # filter the candidates if extra cols need to be compared
    def count_extra_clauses(self, node, candidate_table):
        clauses_cols = self.c_extra_cols()
        clauses_comparison = self.c_extra_cols_comparison()

        if clauses_cols:
            clauses = []
            for i in range(len(clauses_cols)):
                clauses.append("{} = (SELECT {} FROM {} AS c2 {})".format(
                    clauses_cols[i], clauses_comparison[i],
                    candidate_table,
                    self.extra_clauses_filter(node)))

            return " AND ".join(clauses)
        else:
            return ""

    # Join the candidate tables correctly
    def extra_clauses_filter_join(self,node):
        return [f"c2.{var2col(v)} = candidate.{var2col(v)}" for v in node.stored_vertices]




    def extra_clauses_filter(self,node):
        node_filter = self.c_filter_problem(node)
        if node_filter:
            node_filter += " AND {}".format(" AND ".join(self.extra_clauses_filter_join(node)))
            return node_filter
        else:
            values_filter = self.extra_clauses_filter_join(node)
            if values_filter:
                return "WHERE {}".format(" AND ".join(self.extra_clauses_filter_join(node)))
            else:
                return ""



def var2cnt(node,var):
    if node.needs_introduce(var):
        return "1"
    else:
        return "{}.count".format(var2tab_alias(node,var))

def node2cnt(node):
    return "{}.count".format(node2tab_alias(node))

def node2tab(node):
    return f"td_node_{node.id}"

def node2tab_alias(node):
    return f"t{node.id}"

def var2tab(node, var):
    if node.needs_introduce(var):
        return "introduce"
    else:
        return node2tab(node.vertex_children(var)[0])

def var2tab_alias(node, var):
    if node.needs_introduce(var):
        return f"i{var}"
    else:
        return node2tab_alias(node.vertex_children(var)[0])

def var2col(var):
    return f"v{var}"