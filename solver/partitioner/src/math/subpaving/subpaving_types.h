/*++
Copyright (c) 2012 Microsoft Corporation

Module Name:

    subpaving_types.h

Abstract:

    Subpaving auxiliary types.

Author:

    Leonardo de Moura (leonardo) 2012-08-07.

Revision History:

--*/
#pragma once

namespace subpaving {

typedef unsigned var;

const var null_var = UINT_MAX;

class atom;

enum lit_type {
    bool_lit = 0,
    eq_lit = 1,
    ineq_lit = 2
};

struct lit {
    var    m_x;
    unsigned    m_lower:1;
    unsigned    m_open:1;
    unsigned    m_bool:1;
    unsigned    m_int:1;    
    mpq *       m_val;
    // atom *       m_a;
    void reset() { m_x = null_var; }
    lit() { reset(); }
    lit_type get_type() const { return m_bool ? (m_open ? eq_lit : bool_lit) : ineq_lit; }
    bool is_ineq_lit() const { return !m_bool; }
    bool is_eq_lit() const { return m_bool && m_open; }
    bool is_bool_lit() const { return m_bool && !m_open; }
};

struct task_info {
    unsigned m_node_id;
    unsigned m_depth;
    unsigned m_undef_lit_num;
    unsigned m_undef_clause_num;
    vector<vector<lit>> m_clauses;
    vector<lit> m_var_bounds;
    
    var m_splitting_var;
    lit m_split_left_child;
    lit m_split_right_child;
    
    void reset() {
        m_node_id = UINT32_MAX;
        m_clauses.reset();
        m_var_bounds.reset();
        m_undef_lit_num = 0;
        m_undef_clause_num = 0;
    }

    void copy(task_info const & src) {
        m_node_id = src.m_node_id;
        m_depth = src.m_depth;
        m_undef_lit_num = src.m_undef_lit_num;
        m_undef_clause_num = src.m_undef_clause_num;
        m_clauses.reset();
        m_clauses.append(src.m_clauses);
        m_var_bounds.reset();
        m_var_bounds.append(src.m_var_bounds);
    }
};

struct control_message {
    enum P2C {
        debug_info = 0,
        new_unknown_node = 1,
        new_unsat_node = 2,
        sat = 3,
        unsat = 4,
        unknown = 5
    };

    enum C2P {
        unsat_node = 0,
        terminate_node = 1
    };
};


class exception {
};

class power : public std::pair<var, unsigned> {
public:
    power() = default;
    power(var v, unsigned d):std::pair<var, unsigned>(v, d) {}
    var x() const { return first; }
    var get_var() const { return first; }
    unsigned degree() const { return second; }
    unsigned & degree() { return second; }
    void set_var(var x) { first = x; }
    struct lt_proc { bool operator()(power const & p1, power const & p2) { return p1.get_var() < p2.get_var(); } };
};

struct display_var_proc {
    virtual ~display_var_proc() = default;
    virtual void operator()(std::ostream & out, var x) const { out << "x" << x; }
};

}
