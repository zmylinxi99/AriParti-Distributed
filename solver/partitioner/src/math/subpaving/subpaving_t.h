/*++
Copyright (c) 2012 Microsoft Corporation

Module Name:

    subpaving_t.h

Abstract:

    Subpaving template for non-linear arithmetic.

Author:

    Leonardo de Moura (leonardo) 2012-07-31.

Revision History:

--*/
#pragma once

#include "util/tptr.h"
#include "util/small_object_allocator.h"
#include "util/chashtable.h"
#include "util/parray.h"
#include "math/interval/interval.h"
#include "util/scoped_numeral_vector.h"
#include "math/subpaving/subpaving_types.h"
#include "util/params.h"
#include "util/statistics.h"
#include "util/lbool.h"
#include "util/rlimit.h"

#include <ostream>
#include <queue>
#include <random>
#include <cmath>
#include <assert.h>

#ifdef _MSC_VER
#pragma warning(disable : 4200)
#pragma warning(disable : 4355)
#endif

namespace subpaving {

struct config_mpq {
    typedef unsynch_mpq_manager numeral_manager;
    struct exception {};

    static void round_to_minus_inf(numeral_manager & m) {}
    static void round_to_plus_inf(numeral_manager & m) {}
    static void set_rounding(numeral_manager & m, bool to_plus_info) {}
    numeral_manager & m_manager;
    config_mpq(numeral_manager & m):m_manager(m) {}
    numeral_manager & m() const { return m_manager; }
};

class context_t {
public:
    typedef typename config_mpq::numeral_manager       numeral_manager;
    typedef typename numeral_manager::numeral numeral;

    /**
       \brief Atoms used to encode a problem.
    */
    class atom {
        friend class context_t;
        var         m_x;
        numeral     m_val;
        unsigned    m_ref_count:29;
        // (bool, open):
        // (1, 0): bool, (1, 1): eq
        // (0, X): ineq
        unsigned    m_bool:1;
        unsigned    m_open:1;
        unsigned    m_lower:1;
    public:
        var x() const { return m_x; }
        numeral const & value() const { return m_val; }
        bool is_bool() const { return m_bool; }
        bool is_lower() const { return m_lower; }
        bool is_open() const { return m_open; }
        bool is_ineq_atom() const { return !m_bool; }
        bool is_eq_atom() const { return m_bool && m_open; }
        bool is_bool_atom() const { return m_bool && !m_open; }
        void display(std::ostream & out, numeral_manager & nm, display_var_proc const & proc = display_var_proc());
        struct lt_var_proc { 
            bool operator()(atom const * a, atom const * b) const {
                if (a->m_bool != b->m_bool)
                    return a->m_bool;
                return a->m_x < b->m_x;
            }
        };
    };

    class node;

    class constraint {
    public:
        enum kind {
            CLAUSE, MONOMIAL, POLYNOMIAL
            // TODO: add SIN, COS, TAN, ...
        };
    protected:
        kind     m_kind;
        uint64_t m_timestamp;
    public:
        constraint(kind k):m_kind(k), m_timestamp(0) {}
        
        kind get_kind() const { return m_kind; }
        
        // Return the timestamp of the last propagation visit
        uint64_t timestamp() const { return m_timestamp; }
        // Reset propagation visit time
        void set_visited(uint64_t ts) { m_timestamp = ts; }
    };

    /**
       \brief Clauses in the problem description and lemmas learned during paving.
    */
    class clause : public constraint {
        friend class context_t;
        unsigned m_size;            //!< Number of atoms in the clause.
        unsigned m_lemma:1;         //!< True if it is a learned clause.
        unsigned m_watched:1;       //!< True if it we are watching this clause. All non-lemmas are watched.
        unsigned m_num_jst:30;      //!< Number of times it is used to justify some bound.
        atom *   m_atoms[0];
        static unsigned get_obj_size(unsigned sz) { return sizeof(clause) + sz*sizeof(atom*); }
    public:
        clause():constraint(constraint::CLAUSE) {}
        unsigned size() const { return m_size; }
        bool watched() const { return m_watched; }
        atom * operator[](unsigned i) const { SASSERT(i < size()); return m_atoms[i]; }
        void display(std::ostream & out, numeral_manager & nm, display_var_proc const & proc = display_var_proc());
    };

    class justification {
        void * m_data;
    public:
        enum kind {
            AXIOM = 0,
            ASSUMPTION,
            CLAUSE,
            VAR_DEF
        };
        
        justification(bool axiom = true) {
            m_data = axiom ? reinterpret_cast<void*>(static_cast<size_t>(AXIOM)) : reinterpret_cast<void*>(static_cast<size_t>(ASSUMPTION));
        }
        justification(justification const & source) { m_data = source.m_data; }
        explicit justification(clause * c) { m_data = TAG(void*, c, CLAUSE); }
        explicit justification(var x) { m_data = BOXTAGINT(void*, x, VAR_DEF);  }
        
        kind get_kind() const { return static_cast<kind>(GET_TAG(m_data)); }
        bool is_clause() const { return get_kind() == CLAUSE; }
        bool is_axiom() const { return get_kind() == AXIOM; }
        bool is_assumption() const { return get_kind() == ASSUMPTION; }
        bool is_var_def() const { return get_kind() == VAR_DEF; }

        clause * get_clause() const {
            SASSERT(is_clause());
            return UNTAG(clause*, m_data);
        }

        var get_var() const { 
            SASSERT(is_var_def());
            return UNBOXINT(m_data);
        }
        
        bool operator==(justification const & other) const { return m_data == other.m_data;  }
        bool operator!=(justification const & other) const { return !operator==(other); }
    };

    class bound {
        friend class context_t;
        numeral       m_val;
        unsigned      m_x:29;
        unsigned      m_lower:1;
        unsigned      m_open:1;
        unsigned      m_mark:1;
        uint64_t      m_timestamp;
        bound *       m_prev;
        justification m_jst;
        void set_timestamp(uint64_t ts) { m_timestamp = ts; }
    public:
        var x() const { return static_cast<var>(m_x); }
        numeral const & value() const { return m_val; }
        numeral & value() { return m_val; }
        bool is_lower() const { return m_lower; }
        bool is_open() const { return m_open; }
        uint64_t timestamp() const { return m_timestamp; }
        bound * prev() const { return m_prev; }
        justification jst() const { return m_jst; }
        void display(std::ostream & out, numeral_manager & nm, display_var_proc const & proc = display_var_proc());
    };

    struct bound_array_config {
        typedef context_t                value_manager;
        typedef small_object_allocator   allocator;
        typedef bound *                  value;                    
        static const bool ref_count        = false;
        static const bool preserve_roots   = true;
        static const unsigned max_trail_sz = 16;
        static const unsigned factor       = 2;
    };
    
    // auxiliary declarations for parray_manager
    void dec_ref(bound *) {}
    void inc_ref(bound *) {}

    typedef parray_manager<bound_array_config> bound_array_manager;
    typedef typename bound_array_manager::ref  bound_array;

    //#linxi type
    enum bvalue_kind {
        b_conflict = -2,
        b_false,
        b_undef,
        b_true,
        b_arith
    };

    struct bvalue_array_config {
        typedef context_t                value_manager;
        typedef small_object_allocator   allocator;
        typedef bvalue_kind                  value;                    
        static const bool ref_count        = false;
        static const bool preserve_roots   = true;
        static const unsigned max_trail_sz = 16;
        static const unsigned factor       = 2;
    };

    typedef parray_manager<bvalue_array_config> bvalue_array_manager;
    typedef typename bvalue_array_manager::ref  bvalue_array;

    void dec_ref(bvalue_kind) {}
    void inc_ref(bvalue_kind) {}

    /**
       \brief Node in the context_t.
    */
    class node {
        bound_array_manager & m_bm;
        bound_array           m_lowers;
        bound_array           m_uppers;
        bvalue_array_manager & m_bvm;
        bvalue_array          m_bvalue;
        var                   m_conflict;
        unsigned              m_id;
        unsigned              m_depth;
        bound *               m_trail;
        node *                m_parent; //!< parent node
        node *                m_first_child;
        node *                m_next_sibling;
        // Doubly linked list of leaves to be processed
        node *                m_prev;
        node *                m_next;
        unsigned_vector       m_key_rank;
        unsigned_vector       m_split_vars;
        // atoms by unit propagation
        ptr_vector<atom>      m_up_atoms;
    public:
        node(context_t & s, unsigned id, bool_vector &is_bool);
        node(node * parent, unsigned id);
        // return unique identifier.
        unsigned id() const { return m_id; }
        bound_array_manager & bm() const { return m_bm; }
        bvalue_array_manager & bvm() const { return m_bvm; }
        bound_array & lowers() { return m_lowers; }
        bound_array & uppers() { return m_uppers; }
        bool inconsistent() const { return m_conflict != null_var; }
        void set_conflict(var x) { SASSERT(!inconsistent()); m_conflict = x; }
        bound * trail_stack() const { return m_trail; }
        bound * parent_trail_stack() const { return m_parent == nullptr ? nullptr : m_parent->m_trail; }
        bound * lower(var x) const { return bm().get(m_lowers, x); }
        bound * upper(var x) const { return bm().get(m_uppers, x); }

        bvalue_kind bvalue(var x) const { return bvm().get(m_bvalue, x); }
        
        node * parent() const { return m_parent; }
        node * first_child() const { return m_first_child; }
        node * next_sibling() const { return m_next_sibling; }
        node * prev() const { return m_prev; }
        node * next() const { return m_next; }
        /**
           \brief Return true if x is unbounded in this node
        */
        bool is_unbounded(var x) const { return lower(x) == nullptr && upper(x) == nullptr; }
        void push(bound * b);
    
        void set_first_child(node * n) { m_first_child = n; }
        void set_next_sibling(node * n) { m_next_sibling = n; } 
        void set_next(node * n) { m_next = n; }
        void set_prev(node * n) { m_prev = n; }

        unsigned depth() const { return m_depth; }
        
        unsigned_vector & key_rank() { return m_key_rank; }
        unsigned_vector & split_vars() { return m_split_vars; }
        ptr_vector<atom> & up_atoms() { return m_up_atoms; }
    };
    
    /**
       \brief Intervals are just temporary place holders.
       The pavers maintain bounds. 
    */
    struct interval {
        bool   m_constant; // Flag: constant intervals are pairs <node*, var>
        // constant intervals
        node * m_node;
        var    m_x;
        // mutable intervals
        numeral      m_l_val;
        bool         m_l_inf;
        bool         m_l_open;
        numeral      m_u_val;
        bool         m_u_inf;
        bool         m_u_open;
        
        interval():m_constant(false) {}
        void set_constant(node * n, var x) { 
            m_constant = true; 
            m_node = n; 
            m_x = x; 
        }
        void set_mutable() { m_constant = false; }
    };
    
    class interval_config {
    public:
        typedef typename config_mpq::numeral_manager         numeral_manager;
        typedef typename numeral_manager::numeral   numeral;
        typedef typename context_t::interval        interval;
    private:
        numeral_manager & m_manager;
    public:
        interval_config(numeral_manager & m):m_manager(m) {}

        numeral_manager & m() const { return m_manager; }
        void round_to_minus_inf() { config_mpq::round_to_minus_inf(m()); }
        void round_to_plus_inf() {  config_mpq::round_to_plus_inf(m()); }
        void set_rounding(bool to_plus_inf) {  config_mpq::set_rounding(m(), to_plus_inf); }
        numeral const & lower(interval const & a) const {
            if (a.m_constant) {
                bound * b = a.m_node->lower(a.m_x);
                return b == nullptr ? a.m_l_val /* don't care */ : b->value();
            }
            return a.m_l_val;
        }
        numeral const & upper(interval const & a) const {
            if (a.m_constant) {
                bound * b = a.m_node->upper(a.m_x);
                return b == nullptr ? a.m_u_val /* don't care */ : b->value();
            }
            return a.m_u_val;
        }
        numeral & lower(interval & a) { SASSERT(!a.m_constant); return a.m_l_val; }
        numeral & upper(interval & a) { SASSERT(!a.m_constant); return a.m_u_val; }
        bool lower_is_inf(interval const & a) const { return a.m_constant ? a.m_node->lower(a.m_x) == nullptr : a.m_l_inf; }
        bool upper_is_inf(interval const & a) const { return a.m_constant ? a.m_node->upper(a.m_x) == nullptr : a.m_u_inf; }
        bool lower_is_open(interval const & a) const {
            if (a.m_constant) {
                bound * b = a.m_node->lower(a.m_x);
                return b == nullptr || b->is_open();
            }
            return a.m_l_open;
        }
        bool upper_is_open(interval const & a) const {
            if (a.m_constant) {
                bound * b = a.m_node->upper(a.m_x);
                return b == nullptr || b->is_open();
            }
            return a.m_u_open; 
        }
        // Setters
        void set_lower(interval & a, numeral const & n) { SASSERT(!a.m_constant); m().set(a.m_l_val, n); }
        void set_upper(interval & a, numeral const & n) { SASSERT(!a.m_constant); m().set(a.m_u_val, n); }
        void set_lower_is_open(interval & a, bool v) { SASSERT(!a.m_constant); a.m_l_open = v; }
        void set_upper_is_open(interval & a, bool v) { SASSERT(!a.m_constant); a.m_u_open = v; }
        void set_lower_is_inf(interval & a, bool v) { SASSERT(!a.m_constant); a.m_l_inf = v; }
        void set_upper_is_inf(interval & a, bool v) { SASSERT(!a.m_constant); a.m_u_inf = v; }
    };

    typedef ::interval_manager<interval_config> interval_manager;

    class definition : public constraint {
    public:
        definition(typename constraint::kind k):constraint(k) {}
    };

    class monomial : public definition {
        friend class context_t;
        unsigned m_size;
        power    m_powers[0];
        monomial(unsigned sz, power const * pws);
        static unsigned get_obj_size(unsigned sz) { return sizeof(monomial) + sz*sizeof(power); }
    public:
        unsigned size() const { return m_size; }
        power const & get_power(unsigned idx) const { SASSERT(idx < size()); return m_powers[idx]; }
        power const * get_powers() const { return m_powers; }
        var x(unsigned idx) const { return get_power(idx).x(); }
        unsigned degree(unsigned idx) const { return get_power(idx).degree(); }
        void display(std::ostream & out, display_var_proc const & proc = display_var_proc(), bool use_star = false) const;
    };

    class polynomial : public definition {
        friend class context_t;
        unsigned    m_size;
        numeral *   m_as;
        var *       m_xs;
        static unsigned get_obj_size(unsigned sz) { return sizeof(polynomial) + sz*sizeof(numeral) + sz*sizeof(var); }
    public:
        polynomial():definition(constraint::POLYNOMIAL) {}
        unsigned size() const { return m_size; }
        numeral const & a(unsigned i) const { return m_as[i]; }
        var x(unsigned i) const { return m_xs[i]; }
        var const * xs() const { return m_xs; }
        numeral const * as() const { return m_as; }
        void display(std::ostream & out, numeral_manager & nm, display_var_proc const & proc = display_var_proc(), bool use_star = false) const;
    };

    /**
       \brief Watched element (aka occurrence) can be:
       
       - A clause
       - A definition (i.e., a variable)

       Remark: we cannot use the two watched literal approach since we process multiple nodes.
    */
    class watched {
    public:
        enum kind { CLAUSE=0, DEFINITION };
    private:
        void * m_data;
    public:
        watched():m_data(nullptr) {}
        explicit watched(var x) { m_data = BOXTAGINT(void*, x, DEFINITION); }
        explicit watched(clause * c) { m_data = TAG(void*, c, CLAUSE); }
        kind get_kind() const { return static_cast<kind>(GET_TAG(m_data)); }
        bool is_clause() const { return get_kind() != DEFINITION; }
        bool is_definition() const { return get_kind() == DEFINITION; }
        clause * get_clause() const { SASSERT(is_clause()); return UNTAG(clause*, m_data); }
        var get_var() const { SASSERT(is_definition()); return UNBOXINT(m_data); }
        bool operator==(watched const & other) const { return m_data == other.m_data;  }
        bool operator!=(watched const & other) const { return !operator==(other); }
    };

    struct node_info {
        unsigned m_id;
        unsigned m_depth;
        unsigned m_undef_clause_num;
        unsigned m_undef_lit_num;
        node_info(unsigned _id, unsigned _depth, unsigned _ucn, unsigned _uln):
            m_id(_id), m_depth(_depth), m_undef_clause_num(_ucn), m_undef_lit_num(_uln) {}
        // greater means need to split earlier
        // (depth = 1) > (depth = 2)
        // (undef_clause_num = 1) < (undef_clause_num = 2)
        // (undef_lit_num = 1) < (undef_lit_num = 2)
        // (id = 1) > (id = 2)
        bool operator < (const node_info & rhs) const {
            if (m_depth != rhs.m_depth)
                return m_depth > rhs.m_depth;
            if (m_undef_clause_num != rhs.m_undef_clause_num)
                return m_undef_clause_num < rhs.m_undef_clause_num;
            if (m_undef_lit_num != rhs.m_undef_lit_num)
                return m_undef_lit_num < rhs.m_undef_lit_num;
            return m_id > rhs.m_id;
        }
    };

    struct var_info {
        unsigned m_id;
        unsigned m_split_cnt;
        double m_avg_split_cnt;
        // {L, R} (L < 0 or L -> -oo)
        // and    (R > 0 or R -> +oo)
        bool     m_cz; // contain zero
        unsigned m_deg; // max degree
        unsigned m_occ; // occurrence
        numeral m_width;
        double m_width_score;
        bool m_is_too_short;

        double m_score;

        unsigned_vector m_key_rank;
        numeral_manager & m_nm;

        var_info(numeral_manager & _nm) : 
            m_nm(_nm),
            m_is_too_short(false) {
            m_nm.set(m_width, 0);
        }
        
        ~var_info() {
            m_nm.del(m_width);
        }

        // less means better choice
        bool key_lt(unsigned key, const var_info & rhs) const {
            switch (key){
            case 0:
                return m_split_cnt < rhs.m_split_cnt;
            case 1:
                return m_deg > rhs.m_deg;
            case 2:
                return m_cz && !rhs.m_cz;
            case 3:
                return m_occ > rhs.m_occ;
            case 4:
                return m_nm.gt(m_width, rhs.m_width);
            default:
                UNREACHABLE();
            }
            return false;
        }

        bool key_eq(unsigned key, const var_info & rhs) const {
            switch (key){
            case 0:
                return m_split_cnt == rhs.m_split_cnt;
            case 1:
                return m_deg == rhs.m_deg;
            case 2:
                return m_cz == rhs.m_cz;
            case 3:
                return m_occ == rhs.m_occ;
            case 4:
                return m_nm.eq(m_width, rhs.m_width);
            default:
                UNREACHABLE();
            }
            return false;
        }

        // // lhs less than rhs means lhs is a better choice
        // bool operator < (const var_info & rhs) const {
        //     if (m_is_too_short != rhs.m_is_too_short)
        //         return rhs.m_is_too_short;
        //     for (unsigned i : m_key_rank) {
        //         if (i == 0)
        //             continue;
        //         if (!key_eq(i, rhs))
        //             return key_lt(i, rhs);
        //     }
        //     return false;
        // }

        // lhs less than rhs means lhs is a better choice
        bool operator < (const var_info & rhs) const {
            if (m_is_too_short != rhs.m_is_too_short)
                return rhs.m_is_too_short;
            if (m_score != rhs.m_score)
                return m_score > rhs.m_score;
            return m_id < rhs.m_id;
        }

        void copy(const var_info & rhs) {
            m_id = rhs.m_id;
            m_split_cnt = rhs.m_split_cnt;
            m_cz = rhs.m_cz;
            m_deg = rhs.m_deg;
            m_occ = rhs.m_occ;
            m_nm.set(m_width, rhs.m_width);
            m_is_too_short = rhs.m_is_too_short;
            m_score = rhs.m_score;
            m_avg_split_cnt = rhs.m_avg_split_cnt;
            m_width_score = rhs.m_width_score;
        }

        void calc_score() {
            m_score = 1.0;
            if (m_cz)
                m_score *= 2.0;
            m_score *= std::pow(2.0, m_deg);
            m_score *= m_occ;
            m_score /= 2.0 + m_avg_split_cnt;
            m_score *= m_width_score;
        }
        
        std::string to_string() {
            std::stringstream ss;
            ss << "var info: id = " << m_id
               << ", score = " << m_score
               << ", width score = " << m_width_score
               << ", avg_split_cnt = " << m_avg_split_cnt
               << ", split cnt = " << m_split_cnt
               << ", cz = " << m_cz << ", deg = " << m_deg
               << ", occ = " << m_occ
               << ", is too short = " << m_is_too_short
               << ", width = ";
            m_nm.display(ss, m_width);
            return ss.str();
        }
    };

    // struct lit_lt {
    //     numeral_manager & m_nm;
    //     lit_lt(numeral_manager & _nm) : m_nm(_nm) {}
    //     // bool lit, eq lit, ineq lit
    //     bool operator()(const lit & lhs, const lit & rhs) const {
    //         // bool, eq | ineq
    //         if (lhs.m_bool != rhs.m_bool)
    //             return lhs.m_bool;
    //         if (lhs.m_bool) {
    //             // bool | eq
    //             if (lhs.m_open != rhs.m_open)
    //                 return !lhs.m_open;
    //             if (lhs.m_open) {
    //                 // eq
    //                 if (lhs.m_x != rhs.m_x)
    //                     return lhs.m_x < rhs.m_x;
    //                 if (lhs.m_lower != rhs.m_lower)
    //                     return lhs.m_lower < rhs.m_lower;
    //                 return m_nm.lt(*lhs.m_val, *rhs.m_val);
    //             }
    //             else {
    //                 // bool
    //                 if (lhs.m_x != rhs.m_x)
    //                     return lhs.m_x < rhs.m_x;
    //                 return lhs.m_lower;
    //             }
    //         }
    //         else {
    //             // return lhs.m_x < rhs.m_x;
    //             if (lhs.m_x != rhs.m_x)
    //                 return lhs.m_x < rhs.m_x;
    //             if (lhs.m_lower != rhs.m_lower)
    //                 return lhs.m_lower < rhs.m_lower;
    //             return m_nm.lt(*lhs.m_val, *rhs.m_val);
    //         }
    //     }
    // };

    struct lit_lt {
        numeral_manager & m_nm;
        lit_lt(numeral_manager & _nm) : m_nm(_nm) {}
        // bool lit, ineq lit, eq lit
        bool operator()(const lit & lhs, const lit & rhs) const {
            if (lhs.m_x != rhs.m_x)
                return lhs.m_x < rhs.m_x;
            bool lhs_is_bool = lhs.is_bool_lit();
            bool rhs_is_bool = rhs.is_bool_lit();
            if (lhs_is_bool != rhs_is_bool)
                return lhs_is_bool;
            bool lhs_is_ineq = lhs.is_ineq_lit();
            bool rhs_is_ineq = rhs.is_ineq_lit();
            if (lhs_is_ineq != rhs_is_ineq)
                return lhs_is_ineq;
            return false;
        }
    };

    struct arith_lit_lt {
        numeral_manager & m_nm;
        arith_lit_lt(numeral_manager & _nm) : m_nm(_nm) {}
        // bool lit, eq lit, ineq lit
        bool operator()(const lit & lhs, const lit & rhs) const {
            // assert(lhs.m_x == rhs.m_x);
            assert(lhs.m_lower == rhs.m_lower);
            // assert(!lhs.m_bool && !rhs.m_bool);
            // (x < 3), (x > 5)
            if (!m_nm.eq(*lhs.m_val, *rhs.m_val))
                return m_nm.lt(*lhs.m_val, *rhs.m_val);
            // ub: (x <= 3), lb: (x > 3)
            if (lhs.m_lower != rhs.m_lower)
                return !lhs.m_lower;
            if (lhs.m_lower)
                // close: (x >= 3), open: (x > 3)
                return !lhs.m_open;
            else
                // open: (x < 3), close: (x <= 3)
                return lhs.m_open;
        }
    };

    struct ineq_lit_cmp {
        numeral_manager & m_nm;
        ineq_lit_cmp(numeral_manager & _nm) : m_nm(_nm) {}
        // 1 for tighter, 0 for equal, -1 for looser
        int operator()(const lit & lhs, const lit & rhs) const {
            assert(lhs.m_x == rhs.m_x);
            assert(lhs.m_lower == rhs.m_lower);
            if (lhs.m_lower) {
                if (m_nm.gt(*lhs.m_val, *rhs.m_val)) {
                    // lhs: >= 3, rhs: >= 2
                    // >= 3 is tighter than >= 2
                    return 1;
                }
                else if (m_nm.eq(*lhs.m_val, *rhs.m_val)) {
                    if (lhs.m_open == rhs.m_open)
                        return 0;
                    // lhs: > 3, rhs: >= 3
                    // > 3 is tighter than >= 3
                    if (lhs.m_open)
                        return 1;
                    else
                        return -1;
                }
                else {
                    // lhs: > 2, rhs: >= 3
                    // > 2 is not tighter than >= 3
                    return -1;
                }
            }
            else {
                if (m_nm.lt(*lhs.m_val, *rhs.m_val)) {
                    // lhs: <= 2, rhs: <= 3
                    // <= 2 is tighter than <= 3
                    return 1;
                }
                else if (m_nm.eq(*lhs.m_val, *rhs.m_val)) {
                    if (lhs.m_open == rhs.m_open)
                        return 0;
                    // lhs: < 2, rhs: <= 2
                    // < 2 is tighter than <= 2
                    if (lhs.m_open)
                        return 1;
                    else
                        return -1;
                }
                else {
                    // lhs: < 3, rhs: <= 2
                    // < 3 is not tighter than <= 2
                    return -1;
                }
            }
        }
    };

    /**
       \brief Return most recent splitting var for node n.
    */
    var splitting_var(node * n) const;

    /**
       \brief Return true if x is a definition.
    */
    bool is_definition(var x) const { return m_defs[x] != 0; }
    
    typedef svector<watched> watch_list;
    typedef _scoped_numeral_vector<numeral_manager> scoped_numeral_vector;

private:
    reslimit&                 m_limit;
    config_mpq                m_c;
    bool                      m_arith_failed; //!< True if the arithmetic module produced an exception.
    bool                      m_own_allocator;
    small_object_allocator *  m_allocator;
    bound_array_manager       m_bm;
    bvalue_array_manager      m_bvm;
    interval_manager          m_im;
    scoped_numeral_vector     m_num_buffer;

    bool_vector               m_is_int;
    bool_vector               m_is_bool;
    //#linxi bool value: -1: false | 0: undef | 1: true | 2: arith var
    // vector<bvalue_kind>       m_bvalue;
    ptr_vector<definition>    m_defs;
    vector<watch_list>        m_wlist;

    ptr_vector<atom>          m_unit_clauses;
    ptr_vector<clause>        m_clauses;
    ptr_vector<clause>        m_lemmas;
    //#linxi clauses after root node BICP
    bool                      m_root_bicp_done;
    vector<watch_list>        m_bicp_wlist;
    ptr_vector<atom>          m_bicp_unit_clauses;
    ptr_vector<clause>        m_bicp_clauses;

    // vector<watch_list>      * m_ptr_wlist;
    // ptr_vector<atom>        * m_ptr_units;
    // ptr_vector<clause>      * m_ptr_clauses;

    uint64_t                  m_timestamp;
    node *                    m_root;
    // m_leaf_head is the head of a doubly linked list of leaf nodes to be processed.
    node *                    m_leaf_head; 
    node *                    m_leaf_tail;

    var                       m_conflict;
    ptr_vector<bound>         m_queue;
    unsigned                  m_qhead;

    display_var_proc          m_default_display_proc;
    display_var_proc *        m_display_proc;
    

    // Configuration
    numeral                   m_epsilon;         //!< If upper - lower < epsilon, then new bound is not propagated.
    bool                      m_zero_epsilon;
    numeral                   m_max_bound;       //!< Bounds > m_max and < -m_max are not propagated
    numeral                   m_minus_max_bound; //!< -m_max_bound
    numeral                   m_nth_root_prec;   //!< precision for computing the nth root
    unsigned                  m_max_depth;       //!< Maximum depth
    unsigned                  m_max_nodes;       //!< Maximum number of nodes in the tree
    unsigned long long        m_max_memory;      // in bytes

    //#linxi
    unsigned            m_max_propagate;
    unsigned            m_curr_propagate;
    unsigned            m_root_max_prop_time;
    unsigned            m_max_prop_time;

    unsigned            m_rand_seed;
    std::mt19937        m_rand;
    unsigned            m_var_key_num;
    var_info            m_best_var_info;
    var_info            m_curr_var_info;
    numeral             m_small_value_thres;
    numeral             m_unbounded_penalty;
    numeral             m_unbounded_penalty_sq;

    unsigned_vector      m_var_split_candidates;
    
    unsigned_vector      m_var_occs;
    unsigned_vector      m_var_max_deg;
    unsigned_vector      m_var_split_cnt;
    unsigned_vector      m_var_unsolved_split_cnt;
    // double_vector        m_var_split_prob;
    // solving leaf node contribution
    // double_vector        m_var_split_score;
    
    double               m_split_prob_decay;
    numeral             m_split_delta;

    bool                m_init;
    std::string         m_output_dir;
    
    unsigned            m_max_running_tasks;
    unsigned            m_max_alive_tasks;
    
    unsigned            m_read_buffer_len;
    char *              m_read_buffer;
    unsigned            m_read_buffer_head;
    unsigned            m_read_buffer_tail;
    std::string         m_current_line;
    bool                m_partitioner_debug;
    std::stringstream   m_temp_stringstream;
    
    unsigned            m_alive_task_num;
    unsigned            m_unsolved_task_num;
    // ptr_vector<node>    m_alive_tasks;
    
    ptr_vector<node>    m_nodes;
    // bool_vector         m_is_alive;

    enum node_state {
        UNCONVERTED,
        WAITING,
        UNSAT,
        TERMINATED,
    };
    vector<node_state>  m_nodes_state;
    std::priority_queue<node_info> m_leaf_heap;

    //#linxi mpz is a temporary hack
    mpz                       m_max_denominator;
    mpz                       m_adjust_denominator;
    
    node *                  m_last_node;
    task_info *             m_ptask;
    task_info               m_bicp_task;
    // unsigned                m_task_num;
    ptr_buffer<atom>        m_temp_atom_buffer;
    unsigned                m_conj_simplified_cnt;
    unsigned                m_disj_simplified_cnt;
    unsigned                m_skip_clause_cnt;
    // unsigned                m_rm_dom_cnt;
    // random_gen              m_rand;


    // Counters
    unsigned                  m_num_nodes;

    // Statistics
    unsigned                  m_num_conflicts;
    unsigned                  m_num_mk_bounds;
    unsigned                  m_num_splits;
    unsigned                  m_num_visited;
    
    // Temporary
    numeral                   m_tmp1, m_tmp2, m_tmp3;
    mpz                       m_ztmp1;
    interval                  m_i_tmp1, m_i_tmp2, m_i_tmp3;


    friend class node;

    void set_arith_failed() { m_arith_failed = true; }

    void checkpoint();

    bound_array_manager & bm() { return m_bm; }
    bvalue_array_manager & bvm() { return m_bvm; }
    interval_manager & im() { return m_im; }
    small_object_allocator & allocator() const { return *m_allocator; }
    bound * mk_bvar_bound(var x, bool neg, node * n, justification jst);
    void adjust_integer_bound(numeral const &val, numeral &result, bool lower, bool &open);
    void adjust_relaxed_bound(numeral const &val, numeral &result, bool lower, bool &open);
    bound * mk_bound(var x, numeral const & val, bool lower, bool open, node * n, justification jst);
    void del_bound(bound * b);
    // Create a new bound and add it to the propagation queue.
    void propagate_bvar_bound(var x, bool neg, node * n, justification jst);
    void propagate_bound(var x, numeral const & val, bool lower, bool open, node * n, justification jst);

    bool is_int(monomial const * m) const;
    bool is_int(polynomial const * p) const;
    
    bool is_monomial(var x) const { return m_defs[x] != 0 && m_defs[x]->get_kind() == constraint::MONOMIAL; }
    monomial * get_monomial(var x) const { SASSERT(is_monomial(x)); return static_cast<monomial*>(m_defs[x]); }
    bool is_polynomial(var x) const { return m_defs[x] != 0 && m_defs[x]->get_kind() == constraint::POLYNOMIAL; }
    polynomial * get_polynomial(var x) const { SASSERT(is_polynomial(x)); return static_cast<polynomial*>(m_defs[x]); }
    static void display(std::ostream & out, numeral_manager & nm, display_var_proc const & proc, var x, numeral & k, bool lower, bool open);
    void display(std::ostream & out, var x) const;
    void display_definition(std::ostream & out, definition const * d, bool use_star = false) const;
    void display(std::ostream & out, constraint * a, bool use_star = false) const;
    void display(std::ostream & out, bound * b) const;
    void display(std::ostream & out, atom * a) const;
    void display_params(std::ostream & out) const;
    void add_unit_clause(atom * a, bool axiom);
    // Remark: Not all lemmas need to be watched. Some of them can be used to justify clauses only.
    void add_clause_core(unsigned sz, atom * const * atoms, bool lemma, bool watched);
    void del_clause(clause * cls);

    node * mk_node(node * parent = nullptr);
    void del_node(node * n);
    void del_nodes();

    void del(interval & a);
    void del_clauses(ptr_vector<clause> & cs);
    void del_unit_clauses();
    void del_clauses();
    void del_monomial(monomial * m);
    void del_sum(polynomial * p);
    void del_definitions();

    /**
       \brief Insert n in the beginning of the doubly linked list of leaves.

       \pre n is a leaf, and it is not already in the list.
    */
    void push_front(node * n);
    
    /**
       \brief Insert n in the end of the doubly linked list of leaves.
       
       \pre n is a leaf, and it is not already in the list.
    */
    void push_back(node * n);
    
    /**
       \brief Remove n from the doubly linked list of leaves.

       \pre n is a leaf, and it is in the list.
    */
    void remove_from_leaf_dlist(node * n);
    
    /**
       \brief Remove all nodes from the leaf dlist.
    */
    void reset_leaf_dlist();
    
    /**
       \brief Add all leaves back to the leaf dlist.
    */
    void rebuild_leaf_dlist(node * n);

    // -----------------------------------
    //
    // Propagation
    //
    // -----------------------------------

    /**
       \brief Return true if the given node is in an inconsistent state. 
    */
    bool inconsistent(node * n) const { return n->inconsistent(); }

    /**
       \brief Set a conflict produced by the bounds of x at the given node.
    */
    void set_conflict(var x, node * n);

    /**
       \brief Return true if bound b may propagate a new bound using constraint c at node n.
    */
    bool may_propagate(bound * b, constraint * c, node * n);

    /**
       \brief Normalize bound if x is integer.
       
       Examples:
       x < 2     --> x <= 1
       x <= 2.3  --> x <= 2
    */
    void normalize_bound(var x, const numeral &val, numeral &result, bool lower, bool &open);
    void normalize_bound(var x, numeral & val, bool lower, bool & open);

    /**
       \brief Return true if (x, k, lower, open) is a relevant new bound at node n.
       That is, it improves the current bound, and satisfies m_epsilon and m_max_bound.
    */
    bool relevant_new_bound(var x, numeral const & k, bool lower, bool open, node * n);

    bool improve_bvar_bound(var x, bool neg, node * n);
    bool improve_bound(var x, numeral const & k, bool lower, bool open, node * n);

    /**
       \brief Return true if the lower and upper bounds of x are 0 at node n.
    */
    bool is_zero(var x, node * n) const;

    /**
       \brief Return true if upper bound of x is 0 at node n.
    */
    bool is_upper_zero(var x, node * n) const;

    bool conflicting_bvar_bounds(var x, node * n) const;

    /**
       \brief Return true if lower and upper bounds of x are conflicting at node n. That is, upper(x) < lower(x)
    */
    bool conflicting_bounds(var x, node * n) const;

    /**
       \brief Return true if x is unbounded at node n.
    */
    bool is_unbounded(var x, node * n) const { return n->is_unbounded(x); }

    /**
       \brief Return true if b is the most recent lower/upper bound for variable b->x() at node n.
    */
    bool most_recent(bound * b, node * n) const;

    /**
       \brief Add most recent bounds of node n into the propagation queue.
       That is, all bounds b s.t. b is in the trail of n, but not in the tail of parent(n), and most_recent(b, n).
    */
    void add_recent_bounds(node * n);

    // void add_unpropagated_bounds(node * n);

    /**
       \brief Propagate new bounds at node n using get_monomial(x)
       \pre is_monomial(x)
    */
    void propagate_monomial(var x, node * n);
    void propagate_monomial_upward(var x, node * n);
    void propagate_monomial_downward(var x, node * n, unsigned i);

    /**
       \brief Propagate new bounds at node n using get_polynomial(x)
       \pre is_polynomial(x)
    */
    void propagate_polynomial(var x, node * n);
    // Propagate a new bound for y using the polynomial associated with x. x may be equal to y.
    void propagate_polynomial(var x, node * n, var y);

    /**
       \brief Propagate new bounds at node n using clause c.
    */
    void propagate_clause(clause * c, node * n);
    
    /**
       \brief Return the truth value of atom t at node n.
    */
    lbool value(atom * t, node * n);

    lbool value(lit & l, node * n);

    /**
       \brief Propagate new bounds at node n using the definition of variable x.
       \pre is_definition(x)
    */
    void propagate_def(var x, node * n);

    void propagate_bvar(node * n, bound * b);

    bool is_latest_bound(node * n, var x, uint64_t ts);

    /**
       \brief Propagate constraints in b->x()'s watch list.
    */
    void propagate(node * n, bound * b);
        
    /**
       \brief Perform bound propagation at node n.
    */
    void propagate(node * n);
    
    /**
       \brief Try to propagate at node n using all definitions.
    */
    void propagate_all_definitions(node * n);

    // -----------------------------------
    //
    // Main
    //
    // -----------------------------------
    void init();

    /**
       \brief Assert unit clauses in the node n.
    */
    void assert_units(node * n);

    //#linxi

    void init_communication();

    void init_partition();
    
    lit convert_atom_to_lit(atom * a);
    
    bool test_dominated(vector<lit> & longer_cla, vector<lit> & shorter_cla);

    void remove_dominated_clauses(vector<vector<lit>> & input, vector<vector<lit>> & output);
    
    bool simplify_ineqs_in_clause(vector<lit> & input, vector<lit> & output, bool is_conjunction);

    // void convert_node_task_to_task(node * n);

    bool convert_node_to_task(node * n);

    void convert_root_to_task();
    
    /**
       \brief Collect variable informatiion in current node by dp.
    */
    void collect_task_var_info();
    
    void select_best_var(node * n);
    
    void split_node(node * n);

    void write_ss_line_to_coordinator();
    
    void write_line_to_coordinator(const std::string & data);
    
    void write_debug_line_to_coordinator(const std::string & data);

    void write_debug_ss_line_to_coordinator();

    bool read_line_from_coordinator();

    bool update_node_state_unsat(unsigned id);

    void unsat_push_down(node * n);

    bool can_propagate_unsat(node * n);

    void unsat_push_up(node * n);

    void update_split_score(node * n);
    
    void node_solved_unsat(node * n);
    
    void parse_line(const std::string & line);

    // bool read_parse_line();

    void communicate_with_coordinator();

    node * select_next_node();
    
    // void rebuild_clauses_after_bicp();

    // void store_root_task_after_bicp();
    
    bool create_new_task();

    // -----------------------------------
    //
    // Debugging support
    //
    // -----------------------------------
    
    /**
       \brief Return true if b is a bound for node n.
    */
    bool is_bound_of(bound * b, node * n) const;

    /**
       \brief Check the consistency of the doubly linked list of leaves.
    */
    bool check_leaf_dlist() const;

    /**
       \brief Check paving tree structure.
    */
    bool check_tree() const;
    
    /**
       \brief Check main invariants.
    */
    bool check_invariant() const;

public:
    context_t(reslimit& lim, config_mpq const & c, params_ref const & p, small_object_allocator * a);
    ~context_t();

    /**
       \brief Return true if the arithmetic module failed.
    */
    bool arith_failed() const { return m_arith_failed; }
    
    numeral_manager & nm() const { return m_c.m(); }

    unsigned num_vars() const { return m_is_int.size(); }

    bool is_int(var x) const { SASSERT(x < num_vars()); return m_is_int[x]; }

    /**
       \brief Create a new variable.
    */
    var mk_var(bool is_int);
    var mk_bvar();

    /**
       \brief Create the monomial xs[0]^ks[0] * ... * xs[sz-1]^ks[sz-1].
       The result is a variable y s.t. y = xs[0]^ks[0] * ... * xs[sz-1]^ks[sz-1].
       
       \pre for all i \in [0, sz-1] : ks[i] > 0
       \pre sz > 0
    */
    var mk_monomial(unsigned sz, power const * pws);
    
    /**
     * linxi updated, remove constant c
       \brief Create the sum as[0]*xs[0] + ... + as[sz-1]*xs[sz-1].
       The result is a variable y s.t. y = as[0]*xs[0] + ... + as[sz-1]*xs[sz-1].
       
       \pre sz > 0
       \pre for all i \in [0, sz-1] : as[i] != 0
    */
    var mk_sum(unsigned sz, numeral const * as, var const * xs);
    
    /**
       \brief Create an atom.
    */
    atom * mk_bool_atom(var x, bool neg);
    atom * mk_eq_atom(var x, numeral const & k, bool neg);
    atom * mk_ineq_atom(var x, numeral const & k, bool lower, bool open);
    void inc_ref(atom * a);
    void dec_ref(atom * a);
    
    /**
       \brief Assert the clause atoms[0] \/ ... \/ atoms[sz-1]
       \pre sz > 1
    */
    void add_clause(unsigned sz, atom * const * atoms) { add_clause_core(sz, atoms, false, true); }
    
    /**
       \brief Store in the given vector all leaves of the paving tree.
    */
    void collect_leaves(ptr_vector<node> & leaves) const;
    
    /**
       \brief Display constraints asserted in the subpaving.
    */
    void display_constraints(std::ostream & out, bool use_star = false) const;

    std::string lit_to_string(const lit & l) const;

    /**
     * 
       \brief Display bounds for each leaf of the tree.
    */
    void display_bounds(std::ostream & out) const;
    
    void display_bounds(std::ostream & out, node * n) const;

    void set_display_proc(display_var_proc * p) { m_display_proc = p; }

    void set_task_ptr(task_info * p) { m_ptask = p; }

    void updt_params(params_ref const & p);

    static void collect_param_descrs(param_descrs & d);

    void reset_statistics();

    void collect_statistics(statistics & st) const;
    
    lbool operator()();
};

};

