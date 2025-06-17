/*++
Copyright (c) 2012 Microsoft Corporation

Module Name:

    subpaving_t_def.h

Abstract:

    Subpaving template for non-linear arithmetic.

Author:

    Leonardo de Moura (leonardo) 2012-07-31.

Revision History:

--*/
#pragma once

#include "math/subpaving/subpaving_t.h"
#include "math/interval/interval_def.h"
#include "util/buffer.h"
#include "util/z3_exception.h"
#include "util/common_msgs.h"
#include "util/gparams.h"

#include <memory>
#include <thread>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

namespace subpaving {

std::string context_t::lit_to_string(const lit & l) const {
    std::stringstream ss;
    ss << "var[" << l.m_x << "](";
    (*m_display_proc)(ss, l.m_x);
    ss << ")";
    if (l.m_bool) {
        ss << " = ";
        if (l.m_open) {
             ss << nm().to_rational_string(*l.m_val);
        }
        else {
            if (l.m_lower)
                ss << "true";
            else
                ss << "false";
        }
    }
    else {
        if (l.m_lower)
            ss << " >";
        else
            ss << " <";
        if (!l.m_open)
            ss << "=";
        ss << " ";
        ss << nm().to_rational_string(*l.m_val);
    }
    return ss.str();
}

/**
   \brief Auxiliary static method used to display a bound specified by (x, k, lower, open).
*/
void context_t::display(std::ostream & out, numeral_manager & nm, display_var_proc const & proc, var x, numeral & k, bool lower, bool open) {
    if (lower) {
        out << nm.to_rational_string(k) << " <";
        if (!open)
            out << "=";
        out << " ";
        proc(out, x);
    }
    else {
        proc(out, x);
        out << " <";
        if (!open)
            out << "=";
        out << " " << nm.to_rational_string(k);
    }
}

void context_t::atom::display(std::ostream & out, numeral_manager & nm, display_var_proc const & proc) {
    if (m_bool) {
        if (m_open) {
            out << "eq ";
            proc(out, m_x);
            out << " ";
            if (m_lower)
                out << "!";
            out << "= "<< nm.to_rational_string(m_val);
        }
        else {
            out << "bool ";
            proc(out, m_x);
            out << " = ";
            if (m_lower)
                out << "true";
            else
                out << "false";
        }
    }
    else {
        if (m_lower) {
            out << nm.to_rational_string(m_val) << " <";
            if (!m_open)
                out << "=";
            out << " ";
            proc(out, m_x);
        }
        else {
            proc(out, m_x);
            out << " <";
            if (!m_open)
                out << "=";
            out << " " << nm.to_rational_string(m_val);
        }
    }
    // context_t::display(out, nm, proc, m_x, m_val, is_lower(), is_open());
}

void context_t::bound::display(std::ostream & out, numeral_manager & nm, display_var_proc const & proc) {
    context_t::display(out, nm, proc, m_x, m_val, is_lower(), is_open());
}

void context_t::clause::display(std::ostream & out, numeral_manager & nm, display_var_proc const & proc) {
    for (unsigned i = 0; i < size(); i++) {
        if (i > 0)
            out << " or ";
        m_atoms[i]->display(out, nm, proc);
    }
}

context_t::node::node(context_t & s, unsigned id, bool_vector &is_bool):
    m_bm(s.bm()),
    m_bvm(s.bvm())
{
    m_id              = id;
    m_depth           = 0;
    unsigned num_vars = s.num_vars();
    m_conflict        = null_var;
    m_trail           = nullptr;
    m_parent          = nullptr;
    m_first_child     = nullptr;
    m_next_sibling    = nullptr;
    m_prev            = nullptr;
    m_next            = nullptr;
    bm().mk(m_lowers);
    bm().mk(m_uppers);
    for (unsigned i = 0; i < num_vars; i++) {
        bm().push_back(m_lowers, nullptr);
        bm().push_back(m_uppers, nullptr);
        if (is_bool[i])
            bvm().push_back(m_bvalue, bvalue_kind::b_undef);
        else
            bvm().push_back(m_bvalue, bvalue_kind::b_arith);
    }
}

context_t::node::node(node * parent, unsigned id):
    m_bm(parent->m_bm),
    m_bvm(parent->m_bvm)
{
    m_id             = id;
    m_depth          = parent->depth() + 1;
    bm().copy(parent->m_lowers, m_lowers);
    bm().copy(parent->m_uppers, m_uppers);
    bvm().copy(parent->m_bvalue, m_bvalue);
    m_conflict       = parent->m_conflict;
    m_trail          = parent->m_trail;
    m_parent         = parent;
    m_first_child    = nullptr;
    m_next_sibling   = parent->m_first_child;
    m_prev           = nullptr;
    m_next           = nullptr;
    parent->m_first_child = this;

    m_up_atoms.append(parent->m_up_atoms.size(), parent->m_up_atoms.data());
}

/**
   \brief Add a new bound b at this node.
*/
void context_t::node::push(bound * b) {
    SASSERT(b->prev() == m_trail);
    m_trail = b;
    var x = b->x();
    bvalue_kind bk = bvm().get(m_bvalue, x);
    if (bk == bvalue_kind::b_arith) {
        if (b->is_lower()) {
            bm().set(m_lowers, b->x(), b);
            SASSERT(lower(b->x()) == b);
        }
        else {
            bm().set(m_uppers, b->x(), b);
            SASSERT(upper(b->x()) == b);
        }
    }
    else {
        bvalue_kind nbk = b->is_lower() ? b_false : b_true;
        if (bk == bvalue_kind::b_undef) {
            bvm().set(m_bvalue, x, nbk);
        }
        else {
            if (nbk != bk)
                bvm().set(m_bvalue, x, b_conflict);
        }
    }
}

/**
    \brief Return the most recent variable that was used for splitting on node n.
*/
var context_t::splitting_var(node * n) const {
    if (n == m_root)
        return null_var;
    bound * b = n->trail_stack();
    while (b != nullptr) {
        if (b->jst().is_axiom())
            return b->x();
        b = b->prev();
    }
    UNREACHABLE();
    return null_var;
}

context_t::monomial::monomial(unsigned sz, power const * pws):
    definition(constraint::MONOMIAL),
    m_size(sz) {
    std::uninitialized_copy(pws, pws + sz, m_powers);
    std::sort(m_powers, m_powers+sz, typename power::lt_proc());
    DEBUG_CODE({
            for (unsigned i = 0; i < sz; i ++) {
                SASSERT(i == 0 || x(i) > x(i-1));
                SASSERT(degree(i) > 0);
            }});
}

void context_t::monomial::display(std::ostream & out, display_var_proc const & proc, bool use_star) const {
    SASSERT(m_size > 0);
    for (unsigned i = 0; i < m_size; i++) {
        if (i > 0) {
            if (use_star)
                out << "*";
            else
                out << " ";
        }
        proc(out, x(i));
        if (degree(i) > 1)
            out << "^" << degree(i);
    }
}

void context_t::polynomial::display(std::ostream & out, numeral_manager & nm, display_var_proc const & proc, bool use_star) const {
    bool first = true;
    for (unsigned i = 0; i < m_size; i++) {
        if (first)
            first = false;
        else
            out << " + ";
        if (!nm.is_one(a(i))) {
            out << nm.to_rational_string(a(i));
            if (use_star)
                out << "*";
            else
                out << " ";
        }
        proc(out, x(i));
    }
}

context_t::context_t(reslimit& lim, config_mpq const & c, params_ref const & p, small_object_allocator * a):
    m_limit(lim),
    m_c(c),
    m_own_allocator(a == nullptr),
    m_allocator(a == nullptr ? alloc(small_object_allocator, "subpaving") : a),
    m_bm(*this, *m_allocator),
    m_bvm(*this, *m_allocator),
    m_init(false),
    m_best_var_info(nm()),
    m_curr_var_info(nm()),
    m_root_bicp_done(false),
    m_im(lim, interval_config(m_c.m())),
    m_num_buffer(nm())
{
    m_parti_debug = false;
    //#linxi debug
    // m_parti_debug = true;

    m_arith_failed  = false;
    m_timestamp     = 0;
    m_root          = nullptr;
    m_leaf_head     = nullptr;
    m_leaf_tail     = nullptr;
    m_conflict      = null_var;
    m_qhead         = 0;
    m_display_proc  = &m_default_display_proc;

    m_num_nodes     = 0;
    updt_params(p);
    reset_statistics();

    // m_ptr_wlist = &m_wlist;
    // m_ptr_units = &m_unit_clauses;
    // m_ptr_clauses = &m_clauses;
}

context_t::~context_t() {
    nm().del(m_epsilon);
    nm().del(m_max_bound);
    nm().del(m_split_delta);
    nm().del(m_unbounded_penalty);
    nm().del(m_unbounded_penalty_sq);
    nm().del(m_minus_max_bound);
    nm().del(m_nth_root_prec);
    nm().del(m_max_denominator);
    nm().del(m_adjust_denominator);
    nm().del(m_tmp1);
    nm().del(m_tmp2);
    nm().del(m_tmp3);
    nm().del(m_ztmp1);
    del(m_i_tmp1);
    del(m_i_tmp2);
    del(m_i_tmp3);
    del_nodes();
    del_unit_clauses();
    del_clauses();
    del_definitions();
    if (m_own_allocator)
        dealloc(m_allocator);
}

void context_t::checkpoint() {
    if (!m_limit.inc())
        throw default_exception(Z3_CANCELED_MSG);
    if (memory::get_allocation_size() > m_max_memory)
        throw default_exception(Z3_MAX_MEMORY_MSG);
}

void context_t::del(interval & a) {
    nm().del(a.m_l_val);
    nm().del(a.m_u_val);
}

void context_t::updt_params(params_ref const & p) {
    unsigned epsilon = p.get_uint("epsilon", 20);
    if (epsilon != 0) {
        nm().set(m_epsilon, static_cast<int>(epsilon));
        nm().inv(m_epsilon);
        m_zero_epsilon = false;
    }
    else {
        nm().reset(m_epsilon);
        m_zero_epsilon = true;
    }
    
    unsigned max_power = p.get_uint("max_bound", 10);
    nm().set(m_max_bound, 10);
    nm().power(m_max_bound, max_power, m_max_bound);
    nm().set(m_minus_max_bound, m_max_bound);
    nm().neg(m_minus_max_bound);

    // max denominator 10^9
    nm().set(m_max_denominator, 10);
    nm().power(m_max_denominator, 9, m_max_denominator);
    
    // denominator after adjust 10^6
    nm().set(m_adjust_denominator, 10);
    nm().power(m_adjust_denominator, 6, m_adjust_denominator);
    

    m_max_depth = p.get_uint("max_depth", 128);
    //#linxi
    // m_max_nodes = p.get_uint("max_nodes", 8192);
    m_max_nodes = p.get_uint("max_nodes", 32);

    m_max_memory = megabytes_to_bytes(p.get_uint("max_memory", UINT_MAX));

    unsigned prec = p.get_uint("nth_root_precision", 8192);
    if (prec == 0)
        prec = 1;
    nm().set(m_nth_root_prec, static_cast<int>(prec));
    nm().inv(m_nth_root_prec);
}

void context_t::collect_param_descrs(param_descrs & d) {
    d.insert("max_nodes", CPK_UINT, "(default: 8192) maximum number of nodes in the subpaving tree.");
    d.insert("max_depth", CPK_UINT, "(default: 128) maximum depth of the subpaving tree.");
    d.insert("epsilon", CPK_UINT, "(default: 20) value k s.t. a new lower (upper) bound for x is propagated only new-lower(x) > lower(k) + 1/k * max(min(upper(x) - lower(x), |lower|), 1) (new-upper(x) < upper(x) - 1/k * max(min(upper(x) - lower(x), |lower|), 1)). If k = 0, then this restriction is ignored.");
    d.insert("max_bound", CPK_UINT, "(default 10) value k s.t. a new upper (lower) bound for x is propagated only if upper(x) > -10^k or lower(x) = -oo (lower(x) < 10^k or upper(x) = oo)");
    d.insert("nth_root_precision", CPK_UINT, "(default 8192) value k s.t. 1/k is the precision for computing the nth root in the subpaving module.");
}

void context_t::display_params(std::ostream & out) const {
    out << "max_nodes  " << m_max_nodes << "\n";
    out << "max_depth  " << m_max_depth << "\n";
    out << "epsilon    " << nm().to_rational_string(m_epsilon) << "\n";
    out << "max_bound  " << nm().to_rational_string(m_max_bound) << "\n";
    out << "max_memory " << m_max_memory << "\n";
}

typename context_t::bound * context_t::mk_bvar_bound(var x, bool neg, node * n, justification jst) {
    SASSERT(!inconsistent(n));
    ++m_num_mk_bounds;
    void * mem = allocator().allocate(sizeof(bound));
    bound * r  = new (mem) bound();
    r->m_x         = x;
    r->m_lower     = neg;
    r->m_mark      = false;
    r->m_timestamp = m_timestamp;
    r->m_prev      = n->trail_stack();
    r->m_jst       = jst;
    n->push(r);
    TRACE("subpaving_mk_bound", tout << "mk_bound: "; display(tout, r); tout << "\ntimestamp: " << r->m_timestamp << "\n";);
    if (conflicting_bvar_bounds(x, n)) {
        {
            m_temp_stringstream << "conflicting bool var " << x << " bound";
            write_debug_ss_line_to_coordinator();
        }
        TRACE("subpaving_mk_bound", tout << "conflict\n"; display_bounds(tout, n););
        set_conflict(x, n);
    }
    ++m_timestamp;
    if (m_timestamp == UINT64_MAX)
        throw subpaving::exception(); // subpaving failed.
    return r;
}

void context_t::adjust_integer_bound(numeral const &val, numeral &result, bool lower, bool &open) {
    // adjust integer bound
    if (!nm().is_int(val)) {
        open = false; // performing ceil/floor
        if (lower)
            nm().ceil(val, result);
        else
            nm().floor(val, result);
    }
    else {
        nm().set(result, val);
    }
    if (open) {
        open = false;
        if (lower)  {
            nm().inc(result);
        }
        else {
            nm().dec(result);
        }
    }
}

void context_t::adjust_relaxed_bound(numeral const &val, numeral &result, bool lower, bool &open) {
    // adjust integer bound
    if (!nm().is_int(val)) {
        open = true; // performing ceil/floor
        if (lower)
            nm().floor(val, result);
        else
            nm().ceil(val, result);
    }
    else
        nm().set(result, val);
}

typename context_t::bound * context_t::mk_bound(var x, numeral const & val, bool lower, bool open, node * n, justification jst) {
    SASSERT(!inconsistent(n));
    m_num_mk_bounds++;
    void * mem = allocator().allocate(sizeof(bound));
    bound * r  = new (mem) bound();
    r->m_x         = x;
    nm().set(r->m_val, val);
    r->m_lower     = lower;
    r->m_open      = open;
    r->m_mark      = false;
    r->m_timestamp = m_timestamp;
    r->m_prev      = n->trail_stack();
    r->m_jst       = jst;
    n->push(r);
    TRACE("subpaving_mk_bound", tout << "mk_bound: "; display(tout, r); tout << "\ntimestamp: " << r->m_timestamp << "\n";);
    if (conflicting_bounds(x, n)) {
        {
            m_temp_stringstream << "conflicting var " << x << " bound";
            write_debug_ss_line_to_coordinator();
        }
        TRACE("subpaving_mk_bound", tout << "conflict\n"; display_bounds(tout, n););
        set_conflict(x, n);
    }
    m_timestamp++;
    if (m_timestamp == UINT64_MAX)
        throw subpaving::exception(); // subpaving failed.
    return r;
}
bool context_t::improve_bvar_bound(var x, bool neg, node * n) {
    bvalue_kind bk = n->bvalue(x);
    bvalue_kind nbk = neg ? b_false : b_true;
    if (bk == bvalue_kind::b_undef)
        return true;
    else if (nbk != bk)
        return true;
    return false;
}

void context_t::propagate_bvar_bound(var x, bool neg, node * n, justification jst) {
    if (!improve_bvar_bound(x, neg, n))
        return;
    TRACE("linxi_subpaving", 
        tout << "propagate_bvar_bound: " << x << ", neg: " << neg << "\n";
    );
    // {
    //     m_temp_stringstream << "propagate_bvar_bound: var-"<< x << ", neg: " << neg;
    //     write_debug_ss_line_to_coordinator();
    // }
    bound * b = mk_bvar_bound(x, neg, n, jst);
    m_queue.push_back(b);
}

void context_t::propagate_bound(var x, numeral const & val, bool lower, bool open, node * n, justification jst) {
    numeral & nval = m_tmp3;
    normalize_bound(x, val, nval, lower, open);
    if (!improve_bound(x, nval, lower, open, n))
        return;
    
    bound * b = mk_bound(x, nval, lower, open, n, jst);
    // {
    //     m_temp_stringstream << "propagate_bound: var-"<< x;
    //     write_debug_ss_line_to_coordinator();

    //     // bound * lb = n->lower(id);
    //     display(m_temp_stringstream, b);
    //     write_debug_ss_line_to_coordinator();
    // }
    m_queue.push_back(b);
    SASSERT(!lower || n->lower(x) == b);
    SASSERT(lower  || n->upper(x) == b);
    SASSERT(is_int(x) || !lower || nm().eq(n->lower(x)->value(), val));
    SASSERT(is_int(x) || lower  || nm().eq(n->upper(x)->value(), val));
    SASSERT(open || !nm().is_int(val) || !lower || nm().eq(n->lower(x)->value(), val));
    SASSERT(open || !nm().is_int(val) || lower  || nm().eq(n->upper(x)->value(), val));
    SASSERT(!lower || nm().ge(n->lower(x)->value(), val));
    SASSERT(lower  || nm().le(n->upper(x)->value(), val));
}

void context_t::del_bound(bound * b) {
    nm().del(b->m_val);
    b->~bound();
    allocator().deallocate(sizeof(bound), b);
}

void context_t::display(std::ostream & out, var x) const {
    if (x == null_var)
        out << "[null]";
    else
        (*m_display_proc)(out, x);
}

void context_t::display(std::ostream & out, bound * b) const {
    b->display(out, nm(), *m_display_proc);
}

void context_t::display(std::ostream & out, atom * a) const {
    a->display(out, nm(), *m_display_proc);
}

void context_t::display_definition(std::ostream & out, definition const * d, bool use_star) const {
    switch (d->get_kind()) {
    case constraint::MONOMIAL:
        static_cast<monomial const *>(d)->display(out, *m_display_proc, use_star);
        break;
    case constraint::POLYNOMIAL:
        static_cast<polynomial const *>(d)->display(out, nm(), *m_display_proc, use_star);
        break;
    default:
        UNREACHABLE();
    };
}

void context_t::display(std::ostream & out, constraint * c, bool use_star) const {
    if (c->get_kind() == constraint::CLAUSE)
        static_cast<clause*>(c)->display(out, nm(), *m_display_proc);
    else
        display_definition(out, static_cast<definition*>(c), use_star);
}

void context_t::display_bounds(std::ostream & out, node * n) const {
    unsigned num = num_vars();
    for (unsigned x = 0; x < num; x++) {
        bound * l = n->lower(x);
        bound * u = n->upper(x);
        if (l != nullptr) {
            display(out, l);
            out << " ";
        }
        if (u != nullptr) {
            display(out, u);
        }
        if (l != nullptr || u != nullptr)
            out << "\n";
    }
}

/**
   \brief Return true if all variables in m are integer.
*/
bool context_t::is_int(monomial const * m) const {
    for (unsigned i = 0; i < m->size(); i++) {
        if (is_int(m->x(i)))
            return true;
    }
    return false;
}

/**
   \brief Return true if all variables in p are integer, and all coefficients in p are integer.
*/
bool context_t::is_int(polynomial const * p) const {
    for (unsigned i = 0; i < p->size(); i++) {
        if (!is_int(p->x(i)) || !nm().is_int(p->a(i))) {
            TRACE("subpaving_is_int", tout << "polynomial is not integer due to monomial at i: " << i << "\n"; tout.flush();
                  display(tout, p->x(i)); tout << " "; nm().display(tout, p->a(i)); tout << "\n";);
            return false;
        }
    }
    return true;
}

var context_t::mk_var(bool is_int) {
    var r = static_cast<var>(m_is_int.size());
    m_is_int.push_back(is_int);
    m_is_bool.push_back(false);
    m_defs.push_back(0);
    m_wlist.push_back(watch_list());
    return r;
}

var context_t::mk_bvar() {
    var r = static_cast<var>(m_is_int.size());
    m_is_int.push_back(false);
    m_is_bool.push_back(true);
    m_defs.push_back(0);
    m_wlist.push_back(watch_list());
    return r;
}

void context_t::del_monomial(monomial * m) {
    unsigned mem_sz = monomial::get_obj_size(m->size());
    m->~monomial();
    allocator().deallocate(mem_sz, m);
}

var context_t::mk_monomial(unsigned sz, power const * pws) {
    SASSERT(sz > 0);
    unsigned mem_sz  = monomial::get_obj_size(sz);
    void * mem       = allocator().allocate(mem_sz);
    monomial * r     = new (mem) monomial(sz, pws);
    var new_var      = mk_var(is_int(r));
    m_defs[new_var]  = r;
    for (unsigned i = 0; i < sz; i++) {
        var x = pws[i].x();
        m_wlist[x].push_back(watched(new_var));
    }
    return new_var;
}

void context_t::del_sum(polynomial * p) {
    unsigned sz = p->size();
    unsigned mem_sz = polynomial::get_obj_size(sz);
    for (unsigned i = 0; i < sz; i++) {
        nm().del(p->m_as[i]);
    }
    p->~polynomial();
    allocator().deallocate(mem_sz, p);
}

var context_t::mk_sum(unsigned sz, numeral const * as, var const * xs) {
    m_num_buffer.reserve(num_vars());
    for (unsigned i = 0; i < sz; i++) {
        SASSERT(xs[i] < num_vars());
        nm().set(m_num_buffer[xs[i]], as[i]);
    }
    unsigned mem_sz  = polynomial::get_obj_size(sz);
    void * mem       = allocator().allocate(mem_sz);
    polynomial * p   = new (mem) polynomial();
    p->m_size        = sz;
    p->m_as          = reinterpret_cast<numeral*>(static_cast<char*>(mem) + sizeof(polynomial));
    p->m_xs          = reinterpret_cast<var*>(reinterpret_cast<char*>(p->m_as) + sizeof(numeral)*sz);
    memcpy(p->m_xs, xs, sizeof(var)*sz);
    std::sort(p->m_xs, p->m_xs+sz);
    for (unsigned i = 0; i < sz; i++) {
        numeral * curr = p->m_as + i;
        new (curr) numeral();
        var x = p->m_xs[i];
        nm().swap(m_num_buffer[x], *curr);
    }
    TRACE("subpaving_mk_sum", tout << "new variable is integer: " << is_int(p) << "\n";);
    var new_var      = mk_var(is_int(p));
    for (unsigned i = 0; i < sz; i++) {
        var x = p->m_xs[i];
        m_wlist[x].push_back(watched(new_var));
    }
    m_defs[new_var]  = p;
    return new_var;
}


//#linxi TBD atom hash cache

typename context_t::atom * context_t::mk_bool_atom(var x, bool neg) {
    void * mem = allocator().allocate(sizeof(atom));
    atom * r   = new (mem) atom();
    r->m_ref_count = 0;
    r->m_bool      = true;
    r->m_open      = false;
    r->m_lower     = neg;

    r->m_x         = x;
    return r;
}

typename context_t::atom * context_t::mk_eq_atom(var x, numeral const & k, bool neg) {
    void * mem = allocator().allocate(sizeof(atom));
    atom * r   = new (mem) atom();
    r->m_ref_count = 0;
    r->m_bool      = true;
    r->m_open      = true;
    r->m_lower     = neg;

    r->m_x         = x;
    nm().set(r->m_val, k);
    return r;
}

typename context_t::atom * context_t::mk_ineq_atom(var x, numeral const & k, bool lower, bool open) {
    void * mem = allocator().allocate(sizeof(atom));
    atom * r   = new (mem) atom();
    r->m_ref_count = 0;
    r->m_bool      = false;
    r->m_lower     = lower;
    r->m_open      = open;

    r->m_x         = x;
    nm().set(r->m_val, k);
    return r;
}

void context_t::inc_ref(atom * a) {
    TRACE("subpaving_ref_count", tout << "inc-ref: " << a << " " << a->m_ref_count << "\n";);
    if (a)
        a->m_ref_count++;
}

void context_t::dec_ref(atom * a) {
    if (a) {
        TRACE("subpaving_ref_count",
              tout << "dec-ref: " << a << " " << a->m_ref_count << "\n";
              a->display(tout, nm());
              tout << "\n";);
        SASSERT(a->m_ref_count > 0);
        a->m_ref_count--;
        if (a->m_ref_count == 0) {
            nm().del(a->m_val);
            a->~atom();
            allocator().deallocate(sizeof(atom), a);
        }
    }
}

void context_t::add_clause_core(unsigned sz, atom * const * atoms, bool lemma, bool watch) {
    SASSERT(lemma || watch);
    SASSERT(sz > 0);
    if (sz == 1) {
        add_unit_clause(atoms[0], true);
        return;
    }

    void * mem = allocator().allocate(clause::get_obj_size(sz));
    clause * c = new (mem) clause();
    c->m_size  = sz;
    for (unsigned i = 0; i < sz; i++) {
        inc_ref(atoms[i]);
        c->m_atoms[i] = atoms[i];
    }
    std::stable_sort(c->m_atoms, c->m_atoms + sz, typename atom::lt_var_proc());
    if (watch) {
        for (unsigned i = 0; i < sz; i++) {
            var x = c->m_atoms[i]->x();
            if (x != null_var && (i == 0 || x != c->m_atoms[i-1]->x()))
                m_wlist[x].push_back(watched(c));
        }
    }
    c->m_lemma   = lemma;
    c->m_num_jst = 0;
    c->m_watched = watch;
    if (!lemma) {
        m_clauses.push_back(c);
        // (*m_ptr_clauses).push_back(c);
    }
    else if (watch) {
        m_lemmas.push_back(c);
    }
    TRACE("subpaving_clause", tout << "new clause:\n"; display(tout, c); tout << "\n";);
}

void context_t::del_clause(clause * c) {
    SASSERT(c->m_num_jst == 0); // We cannot delete a clause that is being used to justify some bound
    bool watch  = c->watched();
    var prev_x  = null_var;
    unsigned sz = c->size();
    for (unsigned i = 0; i < sz; i++) {
        var x = c->m_atoms[i]->x();
        if (watch) {
            if (x != prev_x)
                m_wlist[x].erase(watched(c));
            prev_x = x;
        }
        dec_ref((*c)[i]);
    }
    unsigned mem_sz = clause::get_obj_size(sz);
    c->~clause();
    allocator().deallocate(mem_sz, c);
}

void context_t::add_unit_clause(atom * a, bool axiom) {
    TRACE("subpaving", a->display(tout, nm(), *m_display_proc); tout << "\n";);
    inc_ref(a);
    // if (m_root_bicp_done) {
    //     m_bicp_unit_clauses.push_back(TAG(atom*, a, axiom));
    // }
    // else {
    //     m_unit_clauses.push_back(TAG(atom*, a, axiom));
    // }
    m_unit_clauses.push_back(TAG(atom*, a, axiom));
}

typename context_t::node * context_t::mk_node(node * parent) {
    void * mem = allocator().allocate(sizeof(node));
    node * r;
    if (parent == nullptr) {
        r = new (mem) node(*this, m_num_nodes, m_is_bool);
    }
    else {
        r = new (mem) node(parent, m_num_nodes);
        
        for (unsigned i = 0, sz = parent->depth(); i < sz; ++i)
            r->split_vars().push_back(parent->split_vars()[i]);
    }

    // Add node in the leaf dlist
    push_front(r);
    ++m_num_nodes;
    m_nodes.push_back(r);
    m_nodes_state.push_back(node_state::UNCONVERTED);
    return r;
}

void context_t::del_node(node * n) {
    SASSERT(n->first_child() == 0);

    SASSERT(m_num_nodes > 0);
    m_num_nodes--;

    // disconnect n from list of leaves.
    remove_from_leaf_dlist(n);

    // disconnect n from parent
    node * p = n->parent();
    bound * b = n->trail_stack();
    bound * b_old;
    if (p != nullptr) {
        node * c = p->first_child();
        if (c == n) {
            // n is the first child
            p->set_first_child(n->next_sibling());
        }
        else {
            SASSERT(c->next_sibling() != 0);
            while (c->next_sibling() != n) {
                c = c->next_sibling();
                SASSERT(c->next_sibling() != 0);
            }
            SASSERT(c->next_sibling() == n);
            c->set_next_sibling(n->next_sibling());
        }
        b_old = p->trail_stack();
    }
    else {
        b_old = nullptr;
    }
    while (b != b_old) {
        bound * old = b;
        b = b->prev();
        del_bound(old);
    }
    bm().del(n->uppers());
    bm().del(n->lowers());
    n->~node();
    allocator().deallocate(sizeof(node), n);
}

void context_t::del_nodes() {
    ptr_buffer<node> todo;
    if (m_root == nullptr)
        return;
    todo.push_back(m_root);
    while (!todo.empty()) {
        node * n = todo.back();
        node * c = n->first_child();
        if (c == nullptr) {
            del_node(n);
            todo.pop_back();
        }
        else {
            while (c != nullptr) {
                todo.push_back(c);
                c = c->next_sibling();
            }
        }
    }
}

void context_t::push_front(node * n) {
    SASSERT(n->first_child() == 0);
    SASSERT(n->next() == 0);
    SASSERT(n->prev() == 0);
    n->set_next(m_leaf_head);
    if (m_leaf_head != nullptr) {
        SASSERT(m_leaf_head->prev() == 0);
        m_leaf_head->set_prev(n);
    }
    else {
        SASSERT(m_leaf_head == 0);
        m_leaf_tail = n;
    }
    m_leaf_head = n;
}

void context_t::push_back(node * n) {
    SASSERT(n->first_child() == 0);
    SASSERT(n->next() == 0);
    SASSERT(n->prev() == 0);
    n->set_prev(m_leaf_tail);
    if (m_leaf_tail != nullptr) {
        SASSERT(m_leaf_tail->next() == 0);
        m_leaf_tail->set_next(n);
    }
    else {
        SASSERT(m_leaf_tail == 0);
        m_leaf_head = n;
    }
    m_leaf_tail = n;
}

void context_t::reset_leaf_dlist() {
    // Remove all nodes from the lead doubly linked list
    node * n = m_leaf_head;
    while (n != nullptr) {
        node * next = n->next();
        n->set_next(nullptr);
        n->set_prev(nullptr);
        n = next;
    }
    m_leaf_head = nullptr;
    m_leaf_tail = nullptr;
}

void context_t::rebuild_leaf_dlist(node * n) {
    reset_leaf_dlist();
    // Reinsert all leaves in the leaf dlist.
    ptr_buffer<node, 1024> todo;
    if (m_root != nullptr)
        todo.push_back(m_root);
    while (!todo.empty()) {
        node * n = todo.back();
        todo.pop_back();
        node * c = n->first_child();
        if (c == nullptr) {
            if (!n->inconsistent())
                push_front(n);
        }
        else  {
            while (c != nullptr) {
                SASSERT(c->parent() == n);
                todo.push_back(c);
                c = c->next_sibling();
            }
        }
    }
}

void context_t::remove_from_leaf_dlist(node * n) {
    node * prev = n->prev();
    node * next = n->next();
    SASSERT(prev == 0 || prev != next);
    SASSERT(next == 0 || prev != next);
    SASSERT(prev != n); SASSERT(next != n);
    if (prev != nullptr) {
        SASSERT(m_leaf_head != n);
        prev->set_next(next);
        n->set_prev(nullptr);
    }
    else if (m_leaf_head == n) {
        m_leaf_head = next;
    }

    if (next != nullptr) {
        SASSERT(m_leaf_tail != n);
        next->set_prev(prev);
        n->set_next(nullptr);
    }
    else if (m_leaf_tail == n) {
        m_leaf_tail = prev;
    }
    SASSERT(n->prev() == 0 && n->next() == 0);
}

void context_t::collect_leaves(ptr_vector<node> & leaves) const {
    // Copy all leaves to the given vector.
    ptr_buffer<node, 1024> todo;
    if (m_root != nullptr)
        todo.push_back(m_root);
    while (!todo.empty()) {
        node * n = todo.back();
        todo.pop_back();
        node * c = n->first_child();
        if (c == nullptr) {
            if (!n->inconsistent())
                leaves.push_back(n);
        }
        else  {
            while (c != nullptr) {
                SASSERT(c->parent() == n);
                todo.push_back(c);
                c = c->next_sibling();
            }
        }
    }
}

void context_t::del_unit_clauses() {
    unsigned sz = m_unit_clauses.size();
    for (unsigned i = 0; i < sz; i++)
        dec_ref(UNTAG(atom*, m_unit_clauses[i]));
    m_unit_clauses.reset();
}

void context_t::del_clauses(ptr_vector<clause> & cs) {
    unsigned sz = cs.size();
    for (unsigned i = 0; i < sz; i++) {
        del_clause(cs[i]);
    }
    cs.reset();
}

void context_t::del_clauses() {
    del_clauses(m_clauses);
    del_clauses(m_lemmas);
}

void context_t::del_definitions() {
    unsigned sz = num_vars();
    for (unsigned i = 0; i < sz; i++) {
        definition * d = m_defs[i];
        if (d == nullptr)
            continue;
        switch (d->get_kind()) {
        case constraint::MONOMIAL:
            del_monomial(static_cast<monomial*>(d));
            break;
        case constraint::POLYNOMIAL:
            del_sum(static_cast<polynomial*>(d));
            break;
        default:
            UNREACHABLE();
            break;
        }
    }
}

void context_t::display_constraints(std::ostream & out, bool use_star) const {
    // display definitions
    out << "definitions:\n";
    for (unsigned i = 0; i < num_vars(); i++) {
        if (is_definition(i)) {
            (*m_display_proc)(out, i);
            out << " = ";
            display_definition(out, m_defs[i], use_star);
            out << "\n";
        }
    }
    // display units
    out << "units:\n";
    for (unsigned i = 0; i < m_unit_clauses.size(); i++) {
        atom * a = UNTAG(atom*, m_unit_clauses[i]);
        a->display(out, nm(), *m_display_proc); out << "\n";
    }
    // display clauses
    out << "clauses:\n";
    for (unsigned i = 0; i < m_clauses.size(); i++) {
        m_clauses[i]->display(out, nm(), *m_display_proc); out << "\n";
    }
}

// -----------------------------------
//
// Propagation
//
// -----------------------------------

void context_t::set_conflict(var x, node * n) {
    m_num_conflicts++;
    n->set_conflict(x);
    // remove_from_leaf_dlist(n);
}

bool context_t::may_propagate(bound * b, constraint * c, node * n) {
    SASSERT(b != 0 && c != 0);
    TRACE("may_propagate_bug", display(tout, b); tout << " | "; display(tout, c); tout << "\nresult: " << (b->timestamp() > c->timestamp()) << ", " << b->timestamp() << ", " << c->timestamp() << "\n";);
    return b->timestamp() >= c->timestamp();
}

// Normalization for bounds (for integer and too large denominator)
void context_t::normalize_bound(var x, const numeral &val, numeral &result, bool lower, bool & open) {
    TRACE("linxi_subpaving",
        tout << "before normalize\n"
             << "x: " << x << ", val: ";
        nm().display(tout, val);
        tout << ", lower: " << lower
             << ", open: " << open << "\n";
    );
    
    if (is_int(x)) {
        // adjust integer bound
        // {
        //     m_temp_stringstream << "before normalize";
        //     write_debug_ss_line_to_coordinator();

        //     m_temp_stringstream << "x: " << x << ", val: ";
        //     nm().display(m_temp_stringstream, val);
        //     m_temp_stringstream << ", lower: " << lower
        //                         << ", open: " << open;
        //     write_debug_ss_line_to_coordinator();
        // }
        adjust_integer_bound(val, result, lower, open);
        // {
        //     m_temp_stringstream << "after normalize";
        //     write_debug_ss_line_to_coordinator();

        //     m_temp_stringstream << "x: " << x << ", val: ";
        //     nm().display(m_temp_stringstream, result);
        //     m_temp_stringstream << ", lower: " << lower
        //                         << ", open: " << open;
        //     write_debug_ss_line_to_coordinator();
        // }
    }
    else {
        mpz &deno = m_ztmp1;
        nm().get_denominator(val, deno);
        if (nm().gt(deno, m_max_denominator)) {
            numeral &nval = m_tmp1;
            nm().mul(m_adjust_denominator, val, nval);
            adjust_relaxed_bound(nval, result, lower, open);
            nm().div(result, m_adjust_denominator, result);
        }
        else {
            nm().set(result, val);
        }
    }
    
    TRACE("linxi_subpaving",
        tout << "after normalize\n"
             << "x: " << x << ", val: ";
        nm().display(tout, result);
        tout << ", lower: " << lower
             << ", open: " << open << "\n";
        tout << "(result, val) lt: " << nm().lt(result, val)
             << ", eq: " << nm().eq(result, val)
             << ", gt: " << nm().gt(result, val) << "\n";
    );
}

void context_t::normalize_bound(var x, numeral & val, bool lower, bool & open) {
    normalize_bound(x, val, val, lower, open);
}

bool context_t::relevant_new_bound(var x, numeral const & k, bool lower, bool open, node * n) {
    try {
        bound * curr_lower = n->lower(x);
        bound * curr_upper = n->upper(x);
        SASSERT(curr_lower == 0 || curr_lower->x() == x);
        SASSERT(curr_upper == 0 || curr_upper->x() == x);
        TRACE("subpaving_relevant_bound",
              display(tout, x); tout << " " << (lower ? ">" : "<") << (open ? "" : "=") << " "; nm().display(tout, k); tout << "\n";
              tout << "existing bounds:\n";
              if (curr_lower) { display(tout, curr_lower); tout << "\n"; }
              if (curr_upper) { display(tout, curr_upper); tout << "\n"; });
        if (lower) {
            // If new bound triggers a conflict, then it is relevant.
            if (curr_upper && (nm().gt(k, curr_upper->value()) || ((open || curr_upper->is_open()) && nm().eq(k, curr_upper->value())))) {
                TRACE("subpaving_relevant_bound", tout << "relevant because triggers conflict.\n";);
                return true;
            }
            // If m_epsilon is zero, then bound is relevant only if it improves existing bound.
            if (m_zero_epsilon && curr_lower != nullptr && (nm().lt(k, curr_lower->value()) || ((curr_lower->is_open() || !open) && nm().eq(k, curr_lower->value())))) {
                // new lower bound does not improve existing bound
                TRACE("subpaving_relevant_bound", tout << "irrelevant because does not improve existing bound.\n";);
                return false;
            }
            if (curr_upper == nullptr && nm().lt(m_max_bound, k)) {
                // new lower bound exceeds the :max-bound threshold
                TRACE("subpaving_relevant_bound", tout << "irrelevant because exceeds :max-bound threshold.\n";);
                return false;
            }
            if (!m_zero_epsilon && curr_lower != nullptr) {
                // check if:
                // new-lower > lower + m_epsilon * max(min(upper - lower, |lower|), 1)
                numeral & min       = m_tmp1;
                numeral & abs_lower = m_tmp2;
                nm().set(abs_lower, curr_lower->value());
                nm().abs(abs_lower);
                if (curr_upper != nullptr) {
                    nm().sub(curr_upper->value(), curr_lower->value(), min);
                    if (nm().lt(abs_lower, min))
                        nm().set(min, abs_lower);
                }
                else {
                    nm().set(min, abs_lower);
                }
                numeral & delta    = m_tmp3;
                nm().set(delta, 1);
                if (nm().gt(min, delta))
                    nm().set(delta, min);
                nm().mul(delta, m_epsilon, delta);
                nm().add(curr_lower->value(), delta, delta);
                TRACE("subpaving_relevant_bound_bug",
                      tout << "k: "; nm().display(tout, k);
                      tout << ", delta: "; nm().display(tout, delta); tout << "\n";
                      tout << "curr_lower: "; nm().display(tout, curr_lower->value());
                      tout << ", min: "; nm().display(tout, min); tout << "\n";);
                if (nm().le(k, delta)) {
                    TRACE("subpaving_relevant_bound", tout << "irrelevant because does not improve existing bound to at least ";
                          nm().display(tout, delta); tout << "\n";);
                    return false;
                }
            }
        }
        else {
            // If new bound triggers a conflict, then it is relevant.
            if (curr_lower && (nm().gt(curr_lower->value(), k) || ((open || curr_lower->is_open()) && nm().eq(k, curr_lower->value())))) {
                TRACE("subpaving_relevant_bound", tout << "relevant because triggers conflict.\n";);
                return true;
            }
            // If m_epsilon is zero, then bound is relevant only if it improves existing bound.
            if (m_zero_epsilon && curr_upper != nullptr && (nm().lt(curr_upper->value(), k) || ((curr_upper->is_open() || !open) && nm().eq(k, curr_upper->value())))) {
                // new upper bound does not improve existing bound
                TRACE("subpaving_relevant_bound", tout << "irrelevant because does not improve existing bound.\n";);
                return false;
            }
            if (curr_lower == nullptr && nm().lt(k, m_minus_max_bound)) {
                // new upper bound exceeds the -:max-bound threshold
                TRACE("subpaving_relevant_bound", tout << "irrelevant because exceeds -:max-bound threshold.\n";);
                return false;
            }
            if (!m_zero_epsilon && curr_upper != nullptr) {
                // check if:
                // new-upper < upper - m_epsilon * max(min(upper - lower, |upper|), 1)
                numeral & min       = m_tmp1;
                numeral & abs_upper = m_tmp2;
                nm().set(abs_upper, curr_upper->value());
                nm().abs(abs_upper);
                if (curr_lower != nullptr) {
                    nm().sub(curr_upper->value(), curr_lower->value(), min);
                    if (nm().lt(abs_upper, min))
                        nm().set(min, abs_upper);
                }
                else {
                    nm().set(min, abs_upper);
                }
                numeral & delta    = m_tmp3;
                nm().set(delta, 1);
                if (nm().gt(min, delta))
                    nm().set(delta, min);
                nm().mul(delta, m_epsilon, delta);
                nm().sub(curr_upper->value(), delta, delta);
                if (nm().ge(k, delta)) {
                    TRACE("subpaving_relevant_bound", tout << "irrelevant because does not improve existing bound to at least ";
                          nm().display(tout, delta); tout << "\n";);
                    return false;
                }
            }
        }
        TRACE("subpaving_relevant_bound", tout << "new bound is relevant\n";);
        return true;
    }
    catch (const typename config_mpq::exception &) {
        // arithmetic module failed.
        set_arith_failed();
        return false;
    }
}

bool context_t::improve_bound(var x, numeral const & k, bool lower, bool open, node * n) {
    bound * curr_lower = n->lower(x);
    bound * curr_upper = n->upper(x);
    SASSERT(curr_lower == 0 || curr_lower->x() == x);
    SASSERT(curr_upper == 0 || curr_upper->x() == x);
    TRACE("subpaving_relevant_bound",
        display(tout, x); tout << " " << (lower ? ">" : "<") << (open ? "" : "=") << " "; nm().display(tout, k); tout << "\n";
        tout << "existing bounds:\n";
        if (curr_lower) { display(tout, curr_lower); tout << "\n"; }
        if (curr_upper) { display(tout, curr_upper); tout << "\n"; }
    );
    if (lower) {
        // If new bound triggers a conflict, then it is relevant.
        if (curr_upper && (nm().gt(k, curr_upper->value()) || ((open || curr_upper->is_open()) && nm().eq(k, curr_upper->value())))) {
            TRACE("subpaving_relevant_bound", tout << "relevant because triggers conflict.\n";);
            return true;
        }
        // Bound is relevant only if it improves existing bound.
        if (curr_lower != nullptr && (nm().lt(k, curr_lower->value()) || ((curr_lower->is_open() || !open) && nm().eq(k, curr_lower->value())))) {
            // new lower bound does not improve existing bound
            TRACE("subpaving_relevant_bound", tout << "irrelevant because does not improve existing bound.\n";);
            return false;
        }
    }
    else {
        // If new bound triggers a conflict, then it is relevant.
        if (curr_lower && (nm().gt(curr_lower->value(), k) || ((open || curr_lower->is_open()) && nm().eq(k, curr_lower->value())))) {
            TRACE("subpaving_relevant_bound", tout << "relevant because triggers conflict.\n";);
            return true;
        }
        // Bound is relevant only if it improves existing bound.
        if (curr_upper != nullptr && (nm().lt(curr_upper->value(), k) || ((curr_upper->is_open() || !open) && nm().eq(k, curr_upper->value())))) {
            // new upper bound does not improve existing bound
            TRACE("subpaving_relevant_bound", tout << "irrelevant because does not improve existing bound.\n";);
            return false;
        }
    }
    TRACE("subpaving_relevant_bound", tout << "new bound is relevant\n";);
    return true;
}

bool context_t::is_zero(var x, node * n) const {
    // Return true if lower(x) == upper(x) == 0 at n
    bound * l = n->lower(x);
    bound * u = n->upper(x);
    return l != nullptr && u != nullptr && nm().is_zero(l->value()) && nm().is_zero(u->value()) && !l->is_open() && !u->is_open();
}

bool context_t::is_upper_zero(var x, node * n) const {
    // Return true if upper(x) is zero at node n
    bound * u = n->upper(x);
    return u != nullptr && nm().is_zero(u->value()) && !u->is_open();
}

bool context_t::conflicting_bvar_bounds(var x, node * n) const {
    // Return true if bvalue[x] == b_conflict
    return n->bvalue(x) == bvalue_kind::b_conflict;
}

bool context_t::conflicting_bounds(var x, node * n) const {
    // Return true if upper(x) < lower(x) at node n
    bound * l = n->lower(x);
    bound * u = n->upper(x);
    return l != nullptr && u != nullptr && (nm().lt(u->value(), l->value()) || ((l->is_open() || u->is_open()) && nm().eq(u->value(), l->value())));
}

/**
   \brief Return the truth value of the atom t in node n.

   The result may be l_true (True), l_false (False), or l_undef(Unknown).
*/
lbool context_t::value(atom * t, node * n) {
    var x = t->x();
    // {
    //     if (x == 4903) {
    //         // linxi: for debugging
    //         m_temp_stringstream << "value(atom* t, node* n): x = 4903, t bool = " << t->m_bool << ", open = " << t->m_open << "\n";
    //         m_temp_stringstream << "t = ";
    //         t->display(m_temp_stringstream, nm(), *m_display_proc);
    //         write_debug_ss_line_to_coordinator();

    //         bound * lb = n->lower(x);
    //         m_temp_stringstream << "x_lower: ";
    //         if (lb == nullptr) {
    //             m_temp_stringstream << "null";
    //         }
    //         else {
    //             display(m_temp_stringstream, lb);
    //         }
    //         write_debug_ss_line_to_coordinator();

    //         bound * ub = n->upper(x);
    //         m_temp_stringstream << "x_upper: ";
    //         if (ub == nullptr) {
    //             m_temp_stringstream << "null";
    //         }
    //         else {
    //             display(m_temp_stringstream, ub);
    //         }
    //         write_debug_ss_line_to_coordinator();
    //     }
    // }
    bvalue_kind bk = n->bvalue(x);
    if (t->m_bool) {
        if (t->m_open) {
            // equation
            // x (!)= 3
            if (is_int(x) && !nm().is_int(t->value())) {
                if (t->is_lower())
                    return l_true;
                return l_false;
            }
            bound * u = n->upper(x);
            bound * l = n->lower(x);
            if (u == nullptr && l == nullptr)
                return l_undef;
            if (u != nullptr && nm().eq(u->value(), t->value()) 
                && l != nullptr && nm().eq(l->value(), t->value())) {
                // bound: x = 3
                if (t->is_lower())
                    return l_false;
                else
                    return l_true;
            }

            if (t->is_lower()) {
                if (u != nullptr && (nm().lt(u->value(), t->value())
                    || (u->is_open() && nm().eq(u->value(), t->value()))))
                    return l_true;
                if (l != nullptr && (nm().gt(l->value(), t->value())
                    || (l->is_open() && nm().eq(l->value(), t->value()))))
                    return l_true;
            }
            else {
                if (u != nullptr && (nm().lt(u->value(), t->value())
                    || (u->is_open() && nm().eq(u->value(), t->value()))))
                    return l_false;
                if (l != nullptr && (nm().gt(l->value(), t->value())
                    || (l->is_open() && nm().eq(l->value(), t->value()))))
                    return l_false;
            }

            // if (t->is_lower()) {
            //     // t: x != 3
            //     if (u != nullptr) {
            //         if (nm().lt(u->value(), t->value())) {
            //             // t: x != 3 and ub: x < 2 -> true
            //             return l_true;
            //         }
            //         if ((u->is_open() && nm().eq(u->value(), t->value()))) {
            //             // t: x != 3 and ub: x < 3 -> true
            //             return l_true;
            //         }
            //     }
                
            //     if (l != nullptr) {
            //         if (nm().gt(l->value(), t->value())) {
            //             // t: x != 3 and lb: x > 4 -> true
            //             return l_true;
            //         }
            //         if ((l->is_open() && nm().eq(l->value(), t->value()))) {
            //             // t: x != 3 and lb: x > 3 -> true
            //             return l_true;
            //         }
            //     }
                
            // }
            // else {
            //     // t: x = 3
            //     if (u != nullptr) {
            //         if (nm().lt(u->value(), t->value())) {
            //             // t: x = 3 and ub: x < 2 -> false
            //             return l_false;
            //         }
            //         if ((u->is_open() && nm().eq(u->value(), t->value()))) {
            //             // t: x = 3 and ub: x < 3 -> false
            //             return l_false;
            //         }
            //     }
            //     if (l != nullptr) {
            //         if (nm().gt(l->value(), t->value())) {
            //             // t: x = 3 and lb: x > 4 -> false
            //             return l_false;
            //         }
            //         if ((l->is_open() && nm().eq(l->value(), t->value()))) {
            //             // t: x = 3 and lb: x > 3 -> false
            //             return l_false;
            //         }
            //     }
            // }

            return l_undef;
        }
        else {
            SASSERT(bk != bvalue_kind::b_arith);
            if (bk == bvalue_kind::b_undef)
                return l_undef;
            // lower means neg
            bvalue_kind nbk = t->m_lower ? b_false : b_true;
            if (bk != nbk)
                return l_false;
            return l_true;
        }
    }
    else {
        SASSERT(bk == bvalue_kind::b_arith);
        bound * u = n->upper(x);
        bound * l = n->lower(x);
        if (u == nullptr && l == nullptr)
            return l_undef;
        else if (t->is_lower()) {
            if (u != nullptr && (nm().lt(u->value(), t->value()) || ((u->is_open() || t->is_open()) && nm().eq(u->value(), t->value()))))
                return l_false;
            else if (l != nullptr && (nm().gt(l->value(), t->value()) || ((l->is_open() || !t->is_open()) && nm().eq(l->value(), t->value()))))
                return l_true;
            else
                return l_undef;
        }
        else {
            if (l != nullptr && (nm().gt(l->value(), t->value()) || ((l->is_open() || t->is_open()) && nm().eq(l->value(), t->value()))))
                return l_false;
            else if (u != nullptr && (nm().lt(u->value(), t->value()) || ((u->is_open() || !t->is_open()) && nm().eq(u->value(), t->value()))))
                return l_true;
            else
                return l_undef;
        }

        // if (u == nullptr && l == nullptr)
        //     return l_undef;
        
        // // t: x ~ 3
        // if (t->is_lower()) {
        //     // t: x >(=) 3
        //     if (u != nullptr) {
        //         // ub: x <(=)
        //         if (nm().lt(u->value(), t->value())) {
        //             // t: x > 3 and ub: x < 2 -> false
        //             return l_false;
        //         }
        //         if ((u->is_open() || t->is_open()) && nm().eq(u->value(), t->value())) {
        //             // only
        //             // t: x >= 3 and ub: x <= 3
        //             // is unknown
        //             return l_false;
        //         }
        //     }

        //     if (l != nullptr) {
        //         // lb: x >(=)
        //         if (nm().gt(l->value(), t->value())) {
        //             // t: x > 3 and lb: x > 4 -> true
        //             return l_true;
        //         }
        //         if ((l->is_open() || !t->is_open()) && nm().eq(l->value(), t->value())) {
        //             // only
        //             // t: x >= 3 and lb: x > 3
        //             // is unknown
        //             return l_true;
        //         }
        //     }
        // }
        // else {
        //     // t: x <(=) 3
        //     if (l != nullptr) {
        //         // lb: x >(=)
        //         if (nm().gt(l->value(), t->value())) {
        //             // t: x < 3 and lb: x > 4 -> false
        //             return l_false;
        //         }
        //         if ((l->is_open() || t->is_open()) && nm().eq(l->value(), t->value())) {
        //             // only
        //             // t: x <= 3 and lb: x >= 3
        //             // is unknown
        //             return l_false;
        //         }
        //     }

        //     if (u != nullptr) {
        //         // ub: x <(=)
        //         if (nm().lt(u->value(), t->value())) {
        //             // t: x < 3 and ub: x < 2 -> true
        //             return l_true;
        //         }
        //         if ((u->is_open() || !t->is_open()) && nm().eq(u->value(), t->value())) {
        //             // only
        //             // t: x <= 3 and ub: x < 3
        //             // is unknown
        //             return l_true;
        //         }
        //     }
        // }
        // return l_undef;
    }
}

/**
   \brief Return the truth value of the test lit tl in node n.

   The result may be l_true (True), l_false (False), or l_undef(Unknown).
*/
lbool context_t::value(lit & tl, node * n) {
    var x = tl.m_x;
    bvalue_kind bk = n->bvalue(x);
    if (tl.m_bool) {
        if (tl.m_open) {
            // equation
            if (is_int(x) && !nm().is_int(*tl.m_val)) {
                if (tl.m_lower)
                    return l_true;
                return l_false;
            }
            bound * u = n->upper(x);
            bound * l = n->lower(x);
            if (u == nullptr && l == nullptr)
                return l_undef;
            if (u != nullptr && nm().eq(u->value(), *tl.m_val) 
                && l != nullptr && nm().eq(l->value(), *tl.m_val)) {
                if (tl.m_lower)
                    return l_false;
                else
                    return l_true;
            }
            if (tl.m_lower) {
                if (u != nullptr && (nm().lt(u->value(), *tl.m_val)
                    || (u->is_open() && nm().eq(u->value(), *tl.m_val))))
                    return l_true;
                if (l != nullptr && (nm().gt(l->value(), *tl.m_val)
                    || (l->is_open() && nm().eq(l->value(), *tl.m_val))))
                    return l_true;
                return l_undef;
            }
            else {
                if (u != nullptr && (nm().lt(u->value(), *tl.m_val)
                    || (u->is_open() && nm().eq(u->value(), *tl.m_val))))
                    return l_false;
                if (l != nullptr && (nm().gt(l->value(), *tl.m_val)
                    || (l->is_open() && nm().eq(l->value(), *tl.m_val))))
                    return l_false;
                return l_undef;
            }
        }
        else {
            SASSERT(bk != bvalue_kind::b_arith);
            if (bk == bvalue_kind::b_undef)
                return l_undef;
            // lower means neg
            bvalue_kind nbk = tl.m_lower ? b_false : b_true;
            if (bk != nbk)
                return l_false;
            return l_true;
        }
    }
    else {
        SASSERT(bk == bvalue_kind::b_arith);
        bound * u = n->upper(x);
        bound * l = n->lower(x);
        if (u == nullptr && l == nullptr)
            return l_undef;
        else if (tl.m_lower) {
            if (u != nullptr && (nm().lt(u->value(), *tl.m_val) || ((u->is_open() || tl.m_open) && nm().eq(u->value(), *tl.m_val))))
                return l_false;
            else if (l != nullptr && (nm().gt(l->value(), *tl.m_val) || ((l->is_open() || !tl.m_open) && nm().eq(l->value(), *tl.m_val))))
                return l_true;
            else
                return l_undef;
        }
        else {
            if (l != nullptr && (nm().gt(l->value(), *tl.m_val) || ((l->is_open() || tl.m_open) && nm().eq(l->value(), *tl.m_val))))
                return l_false;
            else if (u != nullptr && (nm().lt(u->value(), *tl.m_val) || ((u->is_open() || !tl.m_open) && nm().eq(u->value(), *tl.m_val))))
                return l_true;
            else
                return l_undef;
        }
    }
}

void context_t::propagate_clause(clause * c, node * n) {
    TRACE("propagate_clause", tout << "propagate using:\n"; display(tout, c); tout << "\n";);
    m_num_visited++;
    c->set_visited(m_timestamp);
    unsigned sz = c->size();
    unsigned j  = UINT_MAX;
    // {
    //     m_temp_stringstream << "propagate_clause: ";
    //     display(m_temp_stringstream, c);
    //     write_debug_ss_line_to_coordinator();
    //     for (unsigned i = 0; i < sz; i++) {
    //         atom * at = (*c)[i];
    //         m_temp_stringstream << " l[" << i << "] = " << value(at, n);
    //     }
    //     write_debug_ss_line_to_coordinator();
    // }
    for (unsigned i = 0; i < sz; i++) {
        atom * at = (*c)[i];
        TRACE("linxi_subpaving",
            tout << "l[" << i << "] = " << value(at, n) << "\n";
        );
        switch (value(at, n)) {
        case l_true:
            return; // clause was already satisfied at n
        case l_false:
            break;
        case l_undef:
            if (j != UINT_MAX)
                return; // clause has more than one unassigned literal
            j = i;
            break;
        }
    }
    if (j == UINT_MAX) {
        // Clause is in conflict, use first atom to trigger inconsistency
        j = 0;
    }
    else {
        n->up_atoms().push_back((*c)[j]);
    }
    atom * a = (*c)[j];
    TRACE("propagate_clause", tout << "propagating inequality: "; display(tout, a); tout << "\n";);

    if (a->m_bool) {
        if (a->m_open) {
            if (!a->m_lower) {
                propagate_bound(a->x(), a->value(), true, false, n, justification(c));
                if (inconsistent(n))
                    return;
                propagate_bound(a->x(), a->value(), false, false, n, justification(c));
            }
        }
        else
            propagate_bvar_bound(a->x(), a->is_lower(), n, justification(c));
    }
    else {
        propagate_bound(a->x(), a->value(), a->is_lower(), a->is_open(), n, justification(c));
    }
    // A clause can propagate only once.
    // So, we can safely set its timestamp again to avoid another useless visit.
    c->set_visited(m_timestamp);
}

void context_t::propagate_polynomial(var x, node * n, var y) {
    SASSERT(y != null_var);
    SASSERT(is_polynomial(x));
    TRACE("linxi_subpaving",
        tout << "propagate_polynomial:\n";
        tout << "x: "; display(tout, x); tout << "\n";
        tout << "y: "; display(tout, y); tout << "\n";
    );
    polynomial * p = get_polynomial(x);
    unsigned sz    = p->size();
    interval & r   = m_i_tmp1; r.set_mutable();
    interval & v   = m_i_tmp2;
    interval & av  = m_i_tmp3; av.set_mutable();
    if (x == y) {
        for (unsigned i = 0; i < sz; i++) {
            var z = p->x(i);
            v.set_constant(n, z);
            im().mul(p->a(i), v, av);
            if (i == 0)
                im().set(r, av);
            else
                im().add(r, av, r);
        }
        // r contains the deduced bounds for x == y
    }
    else {
        v.set_constant(n, x);
        numeral & a = m_tmp1;
        im().set(r, v);
        for (unsigned i = 0; i < sz; i++) {
            var z = p->x(i);
            if (z != y) {
                v.set_constant(n, z);
                im().mul(p->a(i), v, av);
                im().sub(r, av, r);
            }
            else {
                nm().set(a, p->a(i));
                TRACE("propagate_polynomial_bug", tout << "a: "; nm().display(tout, a); tout << "\n";);
            }
        }
        TRACE("propagate_polynomial_bug", tout << "r before mul 1/a: "; im().display(tout, r); tout << "\n";);
        im().div(r, a, r);
        TRACE("propagate_polynomial_bug", tout << "r after mul 1/a:  "; im().display(tout, r); tout << "\n";);
        // r contains the deduced bounds for y.
    }
    TRACE("linxi_subpaving",
        tout << "interval: ";
        im().display(tout, r);
        tout << "\n"
    );
    // r contains the deduced bounds for y.
    if (!r.m_l_inf) {
        if (relevant_new_bound(y, r.m_l_val, true, r.m_l_open, n)) {
            propagate_bound(y, r.m_l_val, true, r.m_l_open, n, justification(x));
            if (inconsistent(n))
                return;
        }
    }
    if (!r.m_u_inf) {
        if (relevant_new_bound(y, r.m_u_val, false, r.m_u_open, n))
            propagate_bound(y, r.m_u_val, false, r.m_u_open, n, justification(x));
    }
}

void context_t::propagate_polynomial(var x, node * n) {
    TRACE("propagate_polynomial", tout << "propagate_polynomial: "; display(tout, x); tout << "\n";);
    TRACE("propagate_polynomial_detail", display_bounds(tout, n););
    SASSERT(is_polynomial(x));
    polynomial * p = get_polynomial(x);
    p->set_visited(m_timestamp);
    var unbounded_var = null_var;
    if (is_unbounded(x, n))
        unbounded_var = x;
    unsigned sz = p->size();
    for (unsigned i = 0; i < sz; i++) {
        var y = p->x(i);
        if (is_unbounded(y, n)) {
            if (unbounded_var != null_var)
                return; // no propagation is possible.
            unbounded_var = y;
        }
    }
    TRACE("propagate_polynomial", tout << "unbounded_var: "; display(tout, unbounded_var); tout << "\n";);

    if (unbounded_var != null_var) {
        propagate_polynomial(x, n, unbounded_var);
    }
    else {
        propagate_polynomial(x, n, x);
        for (unsigned i = 0; i < sz; i++) {
            if (inconsistent(n))
                return;
            propagate_polynomial(x, n, p->x(i));
        }
    }
}

void context_t::propagate_monomial(var x, node * n) {
    TRACE("propagate_monomial", tout << "propagate_monomial: "; display(tout, x); tout << "\n";);
    SASSERT(is_monomial(x));
    SASSERT(!inconsistent(n));
    monomial * m = get_monomial(x);
    m->set_visited(m_timestamp);
    bool found_unbounded = false;
    bool found_zero      = false;
    bool x_is_unbounded  = false;
    unsigned sz = m->size();
    for (unsigned i = 0; i < sz; i++) {
        var y = m->x(i);
        TRACE("linxi_subpaving",
            tout << "item " << i << ": "; display(tout, y);
            tout << ", found zero: " << found_zero << "\n";
        );
        if (is_zero(y, n)) {
            found_zero = true;
        }
        if (m->degree(i) % 2 == 0) {
            //#linxi found error here
            // if (is_upper_zero(y, n)) {
            //     found_zero = true;
            // }
            continue; // elements with even power always produce a lower bound
        }
        if (is_unbounded(y, n)) {
            found_unbounded = true;
        }
    }
    TRACE("propagate_monomial", tout << "found_zero: " << found_zero << ", found_unbounded: " << found_unbounded << "\n";);
    if (found_zero) {
        if (!is_zero(x, n)) {
            // x must be zero
            numeral & zero = m_tmp1;
            nm().set(zero, 0);
            propagate_bound(x, zero, true,  false, n, justification(x));
            if (inconsistent(n))
                return;
            propagate_bound(x, zero, false, false, n, justification(x));
        }
        // no need to downward propagation
        return;
    }
    x_is_unbounded = n->is_unbounded(x);
    if (!found_unbounded)
        propagate_monomial_upward(x, n);
    if (inconsistent(n))
        return;
    if (!x_is_unbounded) {
        unsigned bad_pos = UINT_MAX;
        interval & aux   = m_i_tmp1;
        for (unsigned i = 0; i < sz; i++) {
            aux.set_constant(n, m->x(i));
            if (im().contains_zero(aux)) {
                if (bad_pos != UINT_MAX)
                    return; // there is more than one position that contains zero, so downward propagation is not possible.
                bad_pos = i;
            }
        }
        TRACE("linxi_subpaving",
            tout << "bad pos: " << bad_pos << "\n";
        );
        if (bad_pos == UINT_MAX) {
            // we can use all variables for downward propagation.
            for (unsigned i = 0; i < sz; i++) {
                if (inconsistent(n))
                    return;
                propagate_monomial_downward(x, n, i);
            }
        }
        else {
            propagate_monomial_downward(x, n, bad_pos);
        }
    }
}

void context_t::propagate_monomial_upward(var x, node * n) {
    SASSERT(is_monomial(x));
    monomial * m = get_monomial(x);
    unsigned sz  = m->size();
    interval & r  = m_i_tmp1; r.set_mutable();
    interval & y  = m_i_tmp2;
    interval & yk = m_i_tmp3; yk.set_mutable();
    for (unsigned i = 0; i < sz; i++) {
        y.set_constant(n, m->x(i));
        im().power(y, m->degree(i), yk);
        if (i == 0)
            im().set(r, yk);
        else
            im().mul(r, yk, r);
    }
    TRACE("linxi_subpaving",
        tout << "interval: ";
        im().display(tout, r);
        tout << "\n"
    );
    // r contains the new bounds for x
    if (!r.m_l_inf) {
        if (relevant_new_bound(x, r.m_l_val, true, r.m_l_open, n)) {
            propagate_bound(x, r.m_l_val, true, r.m_l_open, n, justification(x));
            if (inconsistent(n))
                return;
        }
    }
    if (!r.m_u_inf) {
        if (relevant_new_bound(x, r.m_u_val, false, r.m_u_open, n))
            propagate_bound(x, r.m_u_val, false, r.m_u_open, n, justification(x));
    }
}

void context_t::propagate_monomial_downward(var x, node * n, unsigned j) {
    TRACE("propagate_monomial", tout << "propagate_monomial_downward: "; display(tout, x); tout << ", j: " << j << "\n";
          display(tout, get_monomial(x)); tout << "\n";);
    SASSERT(is_monomial(x));
    monomial * m = get_monomial(x);
    SASSERT(j < m->size());
    unsigned sz = m->size();

    interval & r = m_i_tmp3;
    if (sz > 1) {
        interval & d  = m_i_tmp1; d.set_mutable();
        interval & y  = m_i_tmp2;
        interval & yk = m_i_tmp3; yk.set_mutable();
        bool first = true;
        for (unsigned i = 0; i < sz; i++) {
            if (i == j)
                continue;
            y.set_constant(n, m->x(i));
            im().power(y, m->degree(i), yk);
            if (first) {
                im().set(d, yk);
                first = false;
            }
            else {
                im().mul(d, yk, r);
                im().set(d, r);
            }
        }
        if (im().contains_zero(d)) {
            im().reset_lower(r);
            im().reset_upper(r);
        }
        else {
            interval& aux = m_i_tmp2;
            aux.set_constant(n, x);
            im().div(aux, d, r);
        }
    }
    else {
        SASSERT(sz == 1);
        SASSERT(j == 0);
        interval & aux  = m_i_tmp2;
        aux.set_constant(n, x);
        im().set(r, aux);
    }
    TRACE("linxi_subpaving",
        tout << "interval: ";
        im().display(tout, r);
        tout << "\n"
    );
    unsigned deg = m->degree(j);
    if (deg > 1) {
        if (deg % 2 == 0 && im().lower_is_neg(r))
            return; // If d is even, we can't take the nth-root when lower(r) is negative.
        if (deg > 2)
            return;
        im().xn_eq_y(r, deg, m_nth_root_prec, r);
    }
    var y = m->x(j);
    // r contains the new bounds for y
    if (!r.m_l_inf) {
        if (relevant_new_bound(y, r.m_l_val, true, r.m_l_open, n)) {
            propagate_bound(y, r.m_l_val, true, r.m_l_open, n, justification(x));
            if (inconsistent(n))
                return;
        }
        propagate_bound(y, r.m_l_val, true, r.m_l_open, n, justification(x));
        if (inconsistent(n))
            return;
    }
    if (!r.m_u_inf) {
        if (relevant_new_bound(y, r.m_u_val, false, r.m_u_open, n))
            propagate_bound(y, r.m_u_val, false, r.m_u_open, n, justification(x));
    }
}

bool context_t::most_recent(bound * b, node * n) const {
    var x = b->x();
    if (b->is_lower())
        return n->lower(x) == b;
    else
        return n->upper(x) == b;
}

void context_t::add_recent_bounds(node * n) {
    SASSERT(m_queue.empty());
    bound * old_b = n->parent_trail_stack();
    bound * b     = n->trail_stack();
    while (b != old_b) {
        if (most_recent(b, n)) {
            b->set_timestamp(m_timestamp);
            m_queue.push_back(b);
        }
        b = b->prev();
    }
}

// // void context_t::add_unpropagated_bounds(node * n) {
//     bound * lpb   = n->last_processed_bounds();
//     bound * b     = n->trail_stack();
//     unsigned cnt = 0;
//     unsigned max_lpb;
//     while (b != lpb) {
//         if (most_recent(b, n)) {
//             b->set_timestamp(m_timestamp);
//             m_queue.push_back(b);
//         }
//         b = b->prev();
//     }
// }

void context_t::propagate_def(var x, node * n) {
    SASSERT(is_definition(x));
    m_num_visited++;
    definition * d = m_defs[x];
    switch (d->get_kind()) {
    case constraint::MONOMIAL:
        propagate_monomial(x, n);
        break;
    case constraint::POLYNOMIAL:
        propagate_polynomial(x, n);
        break;
    default:
        break;
    }
}

void context_t::propagate_bvar(node * n, bound * b) {
    var x = b->x();
    TRACE("subpaving_propagate", tout << "propagate: "; display(tout, b); tout << ", timestamp: " << b->timestamp() << "\n";);
    ++m_curr_propagate;
    typename watch_list::const_iterator it  = m_wlist[x].begin();
    typename watch_list::const_iterator end = m_wlist[x].end();
    for (; it != end; ++it) {
        if (inconsistent(n))
            return;
        watched const & w = *it;
        SASSERT(w.is_clause());
        try {
            clause * c = w.get_clause();
            propagate_clause(c, n);
        }
        catch (const typename config_mpq::exception &) {
            // arithmetic module failed, ignore constraint
            set_arith_failed();
        }
    }
}

bool context_t::is_latest_bound(node * n, var x, uint64_t ts) {    
    bound * curr_lower = n->lower(x);
    bound * curr_upper = n->upper(x);
    if (curr_lower != nullptr && curr_lower->timestamp() > ts)
        return false;
    if (curr_upper != nullptr && curr_upper->timestamp() > ts)
        return false;
    return true;
}

void context_t::propagate(node * n, bound * b) {
    var x = b->x();
    if (!is_latest_bound(n, x, b->timestamp()))
        return;
    TRACE("subpaving_propagate", tout << "propagate: "; display(tout, b); tout << ", timestamp: " << b->timestamp() << "\n";);
    ++m_curr_propagate;
    typename watch_list::const_iterator it  = m_wlist[x].begin();
    typename watch_list::const_iterator end = m_wlist[x].end();
    for (; it != end; ++it) {
        if (inconsistent(n))
            return;
        watched const & w = *it;
        try {
            if (w.is_clause()) {
                clause * c = w.get_clause();
                if (may_propagate(b, c, n)) {
                    propagate_clause(c, n);
                }
            }
            else {
                var y = w.get_var();
                definition * d = m_defs[y];
                if (may_propagate(b, d, n)) {
                    propagate_def(y, n);
                }
            }
        }
        catch (const typename config_mpq::exception &) {
            // arithmetic module failed, ignore constraint
            set_arith_failed();
        }
    }
    if (inconsistent(n))
        return;
    if (is_definition(x)) {
        definition * d = m_defs[x];
        if (may_propagate(b, d, n)) {
            propagate_def(x, n);
        }
    }
}

void context_t::propagate(node * n) {
    if (m_parti_debug) {
        m_temp_stringstream << "propagate node #" << n->id() << "\n";
        write_debug_ss_line_to_coordinator();
    }
    m_curr_propagate = 0;
    time_t prop_start = std::time(nullptr);
    // unsigned prop_start = static_cast<unsigned>(std::time(nullptr));
    unsigned prop_time = 0;
    while (!inconsistent(n) && m_qhead < m_queue.size()) {
        // if (m_curr_propagate >= m_max_propagate)
        //     break;

        // prop_time = static_cast<unsigned>(std::time(nullptr)) - prop_start;
        prop_time = static_cast<unsigned>(std::time(nullptr) - prop_start);
        if (n->id() == 0) {
            if (prop_time > m_root_max_prop_time)
                break;
        }
        else {
            if (prop_time > m_max_prop_time)
                break;
        }
        checkpoint();
        bound * b = m_queue[m_qhead];
        m_qhead++;
        SASSERT(is_bound_of(b, n));
        if (m_is_bool[b->x()])
            propagate_bvar(n, b);
        else
            propagate(n, b);
    }
    {
        m_temp_stringstream
            << "node " << n->id()
            << ", propagated cnt: " << m_curr_propagate
            // << "(" << m_max_propagate << ")"
            << ", time: " << prop_time;
        write_debug_ss_line_to_coordinator();
    }
    TRACE("linxi_subpaving", tout << "node #" << n->id() << " after propagation\n";
            display_bounds(tout, n););
    m_queue.reset();
    m_qhead = 0;
}

void context_t::propagate_all_definitions(node * n) {
    unsigned num = num_vars();
    for (unsigned x = 0; x < num; x++) {
        if (inconsistent(n))
            break;
        if (is_definition(x))
            propagate_def(x, n);
    }
}

// -----------------------------------
//
// Main
//
// -----------------------------------

void context_t::assert_units(node * n) {
    typename ptr_vector<atom>::const_iterator it  = m_unit_clauses.begin();
    typename ptr_vector<atom>::const_iterator end = m_unit_clauses.end();
    for (; it != end; ++it) {
        checkpoint();
        atom * a = UNTAG(atom *, *it);
        bool axiom = GET_TAG(*it) != 0;
        TRACE("subpaving_init", tout << "asserting: "; display(tout, a); tout << ", axiom: " << axiom << "\n";);
        if (a->x() == null_var)
            continue;
        if (a->m_bool) {
            if (a->m_open) {
                // eq-TBD
                if (a->m_lower) {
                    UNREACHABLE();
                }
                else {
                    propagate_bound(a->x(), a->value(), true, false, n, justification(axiom));
                    if (inconsistent(n))
                        return;
                    propagate_bound(a->x(), a->value(), false, false, n, justification(axiom));
                }
            }
            else
                propagate_bvar_bound(a->x(), a->is_lower(), n, justification(axiom));
        }
        else {
            propagate_bound(a->x(), a->value(), a->is_lower(), a->is_open(), n, justification(axiom));
        }
        if (inconsistent(n))
            break;
    }
    TRACE("subpaving_init", tout << "bounds after init\n"; display_bounds(tout, n););
}

void context_t::write_line_to_coordinator(const std::string & line) {
    std::cout << line << std::endl;
}

void context_t::write_ss_line_to_coordinator() {
    write_line_to_coordinator(m_temp_stringstream.str());
    m_temp_stringstream.str("");
    m_temp_stringstream.clear();
    // {
    //     m_temp_stringstream << "current time: " << std::time(nullptr);
    //     write_debug_ss_line_to_coordinator();
    // }
}

void context_t::write_debug_line_to_coordinator(const std::string & line) {
    if (!m_partitioner_debug)
        return;
    std::cout << control_message::P2C::debug_info << " " << line << std::endl;
}

void context_t::write_debug_ss_line_to_coordinator() {
    if (!m_partitioner_debug)
        return;
    std::istringstream iss(m_temp_stringstream.str());
    std::string line;
    while (std::getline(iss, line)) {
        write_debug_line_to_coordinator(line);
    }
    m_temp_stringstream.str("");
    m_temp_stringstream.clear();
}

bool context_t::read_line_from_coordinator() {
    if (m_read_buffer_head >= m_read_buffer_tail) {
        ssize_t n = read(STDIN_FILENO, m_read_buffer, m_read_buffer_len - 1);
        if (n > 0) {
            m_read_buffer_head = 0;
            m_read_buffer_tail = static_cast<unsigned>(n);
        }
        else if (n < 0 && errno != EAGAIN) {
            std::cerr << "Error reading input" << std::endl;
            UNREACHABLE();
        }
    }
    
    while (m_read_buffer_head < m_read_buffer_tail) {
        char ch = m_read_buffer[m_read_buffer_head++];
        if (ch == '\n') {
            return true;
        }
        else {
            m_current_line.push_back(ch);
        }
    }
    return false;
}

void context_t::init_communication() {
    // write configuration
    std::ios::sync_with_stdio(false);
    std::cout.setf(std::ios::unitbuf);

    // read configuration
    int flags = fcntl(STDIN_FILENO, F_GETFL, 0);
    fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK);
    
    m_read_buffer_len = (1u << 10);
    m_read_buffer = new char[1024];
    m_read_buffer_head = 0;
    m_read_buffer_tail = 0;
}

void context_t::init_partition() {
    m_init = true;
    m_partitioner_debug = true;
    m_max_propagate = m_is_int.size();

    if (m_max_propagate > 1024)
        m_max_propagate = 1024;
    else if (m_max_propagate < 256u)
        m_max_propagate = 256u;
    
    // second
    m_root_max_prop_time = 10;
    m_max_prop_time = 5;

    m_ptask->reset();
    m_var_occs.resize(num_vars());
    m_var_max_deg.resize(num_vars());
    // m_var_split_cnt.resize(num_vars(), 0);
    // m_var_split_prob.resize(num_vars(), 1.0);
    m_var_unsolved_split_cnt.resize(num_vars(), 0);
    m_split_prob_decay = 0.8;
    m_alive_task_num = 0;
    m_unsolved_task_num = 0;
    m_var_key_num = 5;

    const params_ref &p = gparams::get_ref();
    m_output_dir = p.get_str("output_dir", "ERROR");
    SASSERT(m_output_dir != "ERROR");
    // {
    //     m_temp_stringstream << "output dir: " << m_output_dir;
    //     write_debug_ss_line_to_coordinator();
    // }
    // m_max_running_tasks = p.get_uint("partition_max_running_tasks", 32);
    // m_max_alive_tasks = static_cast<unsigned>(m_max_running_tasks * 1.2) + 2;
    
    nm().set(m_tmp1, 1); // numerator
    nm().set(m_tmp2, 4); // denominator
    nm().div(m_tmp1, m_tmp2, m_small_value_thres);
    nm().set(m_split_delta, 128);
    nm().set(m_unbounded_penalty, 1024);
    nm().set(m_unbounded_penalty_sq, 1024 * 1024);
    
    m_rand_seed = p.get_uint("partition_rand_seed", 0);
    m_rand.seed(m_rand_seed);

    init_communication();

    {
        m_temp_stringstream << "clause number: " << m_clauses.size();
        write_debug_ss_line_to_coordinator();
        
        // m_temp_stringstream << "random seed: " << m_rand_seed;
        // write_debug_ss_line_to_coordinator();
    }
}

void context_t::init() {
    SASSERT(m_root       == 0);
    SASSERT(m_leaf_head  == 0);
    SASSERT(m_leaf_tail  == 0);
    
    m_timestamp = 0;
    m_root      = mk_node();
    SASSERT(m_leaf_head == m_root);
    SASSERT(m_leaf_tail == m_root);
    TRACE("subpaving_init", display_constraints(tout););
    TRACE("linxi_subpaving", 
        tout << "init:\n";
        display_constraints(tout);
    );
    assert_units(m_root);
    propagate_all_definitions(m_root);
    TRACE("subpaving_init", tout << "root bounds after propagation\n"; display_bounds(tout, m_root););
    SASSERT(check_invariant());
}

lit context_t::convert_atom_to_lit(atom * a) {
    lit l;
    l.m_x = a->m_x;
    // l.m_a = a;
    if (a->m_bool) {
        l.m_bool = true;
        l.m_lower = a->m_lower;
        if (a->m_open) {
            l.m_open = true;
            l.m_int = m_is_int[a->m_x];
            l.m_val = &a->m_val;
        }
        else {
            l.m_open = false;
        }
    }
    else {
        l.m_bool = false;
        l.m_int = m_is_int[a->m_x];
        l.m_lower = a->m_lower;
        l.m_open = a->m_open;
        l.m_val = &a->m_val;
    }
    return l;
}

bool context_t::test_dominated(vector<lit> & longer_cla, vector<lit> & shorter_cla) {
    unsigned l_sz = longer_cla.size(), s_sz = shorter_cla.size();
    assert(l_sz >= s_sz);
    unsigned l_p = 0;
    ineq_lit_cmp ilt(nm());
    for (unsigned s_p = 0; s_p < s_sz; ++s_p) {
        lit & s_lit = shorter_cla[s_p];
        bool matched = false;
        while (l_p < l_sz) {
            lit & l_lit = longer_cla[l_p];
            ++l_p;
            lit_type llt = l_lit.get_type();
            lit_type slt = s_lit.get_type();
            if (llt < slt)
                continue;
            if (llt > slt)
                return false;
            if (l_lit.m_x < s_lit.m_x)
                continue;
            if (l_lit.m_x > s_lit.m_x)
                return false;
            if (llt == lit_type::bool_lit) {
                if (l_lit.m_lower != s_lit.m_lower)
                    continue;
                matched = true;
                break;
            }
            else if (llt == lit_type::eq_lit) {
                if (l_lit.m_lower != s_lit.m_lower)
                    continue;
                if (!nm().eq(*l_lit.m_val, *s_lit.m_val))
                    continue;
                matched = true;
                break;
            }
            else {
                if (l_lit.m_lower != s_lit.m_lower)
                    continue;
                // longer  clause: b1 or -b2 or x1 > 1 or x2 < 3
                // shorter clause: b1        or x1 > 1 or x2 < 3 (l_lit equal:  dominated)
                // shorter clause: b1        or x1 > 2 or x2 < 0 (l_lit looser: dominated)
                // l_lit need not tighter than s_lit
                int sgn = ilt(l_lit, s_lit);
                if (sgn == 1)
                    continue;
                matched = true;
                break;
            }
        }
        if (!matched)
            return false;
    }
    return true;
}

void context_t::remove_dominated_clauses(vector<vector<lit>> & input, vector<vector<lit>> & output) {
    const unsigned max_sz_thres = 10000;
    unsigned input_sz = input.size();
    // for (unsigned i = 0; i < input_sz; ++i) {
    //     output.push_back(std::move(input[i]));
    // }
    // return;
    if (input_sz == 0 || input_sz > max_sz_thres) {
        for (unsigned i = 0; i < input_sz; ++i) {
            output.push_back(std::move(input[i]));
        }
        return;
    }
    struct clause_info {
        unsigned id;
        unsigned sz;
        bool operator<(const clause_info & rhs) const {
            if (sz != rhs.sz)
                return sz < rhs.sz;
            return id < rhs.id;
        }
    };
    vector<clause_info> clause_ids;
    for (unsigned i = 0; i < input_sz; ++i) {
        clause_ids.push_back({i, input[i].size()});
    }
    std::sort(clause_ids.begin(), clause_ids.end());
    for (unsigned i = 0; i < input_sz; ++i) {
        vector<lit> & longer_cla = input[clause_ids[i].id];
        bool is_dominated = false;
        for (vector<lit> & shorter_cla : output) {
            if (test_dominated(longer_cla, shorter_cla)) {
                is_dominated = true;
                break;
            }
        }
        if (!is_dominated)
            output.push_back(std::move(longer_cla));
    }
    unsigned removed_cnt = input.size() - output.size();
    if (removed_cnt > 0) {
        m_temp_stringstream
            << "remove_dominated_clauses before: " << input.size()
            << ", after: " << output.size()
            << ", removed: " << removed_cnt;
        write_debug_ss_line_to_coordinator();
    }
}

bool context_t::simplify_ineqs_in_clause(vector<lit> & input, vector<lit> & output, bool is_conjunction) {
    var current_var = null_var;
    bool eq_covered = false;
    lit current_lb, current_ub;
    ineq_lit_cmp ilc(nm());
    
    std::sort(input.begin(), input.end(), lit_lt(nm()));

    // {
    //     m_temp_stringstream << "simplify_ineqs_in_clause before: ";
    //     write_debug_ss_line_to_coordinator();
    //     for (const lit & l : input) {
    //         m_temp_stringstream << "(" << lit_to_string(l) << ") ";
    //     }
    //     write_debug_ss_line_to_coordinator();
    // }

    auto collect_lit_bounds = [](numeral_manager & tnm, vector<lit> & output, lit & current_lb, lit & current_ub, bool is_conjunction, bool eq_covered) {
        if (is_conjunction) {
            if (current_lb.m_x != null_var && current_ub.m_x != null_var) {
                // lb > ub: x > 3 and x < 1   (unsat)
                if (tnm.gt(*current_lb.m_val, *current_ub.m_val)) {
                    output.reset();
                    return true;
                }
                else if (tnm.eq(*current_lb.m_val, *current_ub.m_val)) {
                    // lb == ub:
                    // x > 3  and x < 3   (unsat)
                    // x >= 3 and x < 3   (unsat)
                    // x > 3  and x <= 3  (unsat)
                    if (current_lb.m_open || current_ub.m_open) {
                        output.reset();
                        return true;
                    }
                    // else {
                    // // x >= 3 and x <= 3  (unknown)
                    // //#linxi TBD mk eq lit: x == 3
                    // }
                }
                // else {
                //     // lb < ub: x > 1   and x < 3   (unknown)
                // }
            }
        }
        else {
            if (current_lb.m_x != null_var && current_ub.m_x != null_var) {
                // lb < ub: x > 1   or x < 3   (tautology)
                if (tnm.lt(*current_lb.m_val, *current_ub.m_val)) {
                    output.reset();
                    return true;
                }
                else if (tnm.eq(*current_lb.m_val, *current_ub.m_val)) {
                    // lb == ub:
                    // x >= 3 or x < 3   (tautology)
                    // x > 3  or x <= 3  (tautology)
                    // x >= 3 or x <= 3  (tautology)
                    if (!current_lb.m_open || !current_ub.m_open) {
                        output.reset();
                        return true;
                    }
                    // else {
                    // // lb == ub: x > 3  or x < 3   (unknown)
                    // //#linxi TBD mk ineq lit: x != 3
                    // }
                }
                // else {
                //     // lb > ub: x > 3   or x < 1   (unknown)
                // }
            }
        }
        if (current_lb.m_x != null_var) {
            if (!eq_covered)
                output.push_back(current_lb);
            current_lb.reset();
        }
        if (current_ub.m_x != null_var) {
            if (!eq_covered)
                output.push_back(current_ub);
            current_ub.reset();
        }
        return false;
    };

    for (unsigned i = 0, isz = input.size(); i < isz; ++i) {
        const lit & l = input[i];
        if (current_var != l.m_x) {
            if (collect_lit_bounds(nm(), output, current_lb, current_ub, is_conjunction, eq_covered))
                return true;
            current_var = l.m_x;
            eq_covered = false;
        }
        
        if (l.is_bool_lit()) {
            // TBD boolean literal reduction
            output.push_back(l);
        }
        else if (l.is_ineq_lit()) {
            lit & cb = l.m_lower ? current_lb : current_ub;
            if (cb.m_x == null_var) {
                cb = l;
            }
            else {
                int sgn = ilc(l, cb);
                if (is_conjunction) {
                    if (sgn == 1) {
                        cb = l;
                    }
                }
                else {
                    if (sgn == -1) {
                        cb = l;
                    }
                }
            }
        }
        else if (l.is_eq_lit()) {
            // output.push_back(l);
            if (is_conjunction) {
                // {lb, ub}
                bool contain_val = true;
                if (current_lb.m_x != null_var) {
                    if (nm().gt(*current_lb.m_val, *l.m_val)) {
                        // lb: >= 3, eq: = 2
                        contain_val = false;
                    }
                    else if (nm().eq(*current_lb.m_val, *l.m_val)) {
                        // lb: > 3, eq: = 3
                        if (current_lb.m_open)
                            contain_val = false;
                    }
                }
                if (current_ub.m_x != null_var) {
                    if (nm().lt(*current_ub.m_val, *l.m_val)) {
                        // ub: <= 3, eq: = 4
                        contain_val = false;
                    }
                    else if (nm().eq(*current_ub.m_val, *l.m_val)) {
                        // ub: < 3, eq: = 3
                        if (current_ub.m_open)
                            contain_val = false;
                    }
                }
                if (contain_val) {
                    // [3, 10), x ~ 7
                    if (l.m_lower) {
                        // x != 7
                        output.push_back(l);
                    }
                    else {
                        // x == 7
                        output.push_back(l);
                        eq_covered = true;
                    }
                }
                else {
                    // [3, 10), x ~ 2
                    if (l.m_lower) {
                        // x != 2
                        // do nothing
                    }
                    else {
                        // x == 2 -> unsat
                        output.reset();
                        return true;
                    }
                }
            }
            else {
                // {-inf, ub} or {lb, inf}
                bool contain_val = false;
                if (current_lb.m_x != null_var) {
                    if (nm().lt(*current_lb.m_val, *l.m_val)) {
                        // lb: >= 3, eq: = 4
                        contain_val = true;
                    }
                    else if (nm().eq(*current_lb.m_val, *l.m_val)) {
                        // lb: >= 3, eq: = 3
                        if (!current_lb.m_open)
                            contain_val = true;
                    }
                }
                if (current_ub.m_x != null_var) {
                    if (nm().gt(*current_ub.m_val, *l.m_val)) {
                        // ub: <= 3, eq: = 2
                        contain_val = true;
                    }
                    else if (nm().eq(*current_ub.m_val, *l.m_val)) {
                        // ub: <= 3, eq: = 3
                        if (!current_ub.m_open)
                            contain_val = true;
                    }
                }
                if (contain_val) {
                    // 3] (10, x ~ 2
                    if (l.m_lower) {
                        // x != 2 -> tautology
                        return true;
                    }
                    else {
                        // x == 2
                        // do nothing
                    }
                }
                else {
                    // 3] (10, x ~ 7
                    if (l.m_lower) {
                        // x != 7
                        output.push_back(l);
                        eq_covered = true;
                    }
                    else {
                        // x == 7
                        output.push_back(l);
                    }
                }
            }
            {
                if (eq_covered && current_lb.m_x != null_var && current_ub.m_x != null_var) {
                    m_temp_stringstream << "eq_covered: " << lit_to_string(l);
                    write_debug_ss_line_to_coordinator();
                    if (current_lb.m_x != null_var) {
                        m_temp_stringstream << "current_lb: " << lit_to_string(current_lb);
                        write_debug_ss_line_to_coordinator();
                    }
                    if (current_ub.m_x != null_var) {
                        m_temp_stringstream << "current_ub: " << lit_to_string(current_ub);
                        write_debug_ss_line_to_coordinator();
                    }
                }
            }
        }
        else {
            assert(false);
        }
    }

    if (collect_lit_bounds(nm(), output, current_lb, current_ub, is_conjunction, eq_covered))
        return true;
    
    unsigned reduced = input.size() - output.size();
    // if (reduced > 0) {
    //     m_temp_stringstream << "simplify_ineqs_in_clause: ";
    //     if (is_conjunction)
    //         m_temp_stringstream << "conjunction";
    //     else
    //         m_temp_stringstream << "disjunction";
    //     m_temp_stringstream << ", reduced: " << reduced;
    //     write_debug_ss_line_to_coordinator();
    //     m_temp_stringstream << "input (" << input.size() << "):";
    //     write_debug_ss_line_to_coordinator();
    //     for (const lit & l : input) {
    //         m_temp_stringstream << "(" << lit_to_string(l) << ") ";
    //     }
    //     write_debug_ss_line_to_coordinator();
        
    //     m_temp_stringstream << "output (" << output.size() << "):";
    //     write_debug_ss_line_to_coordinator();
    //     for (const lit & l : output) {
    //         m_temp_stringstream << "(" << lit_to_string(l) << ") ";
    //     }
    //     write_debug_ss_line_to_coordinator();
    // }
    if (is_conjunction)
        m_conj_simplified_cnt += reduced;
    else
        m_disj_simplified_cnt += reduced;
    return false;
}

bool context_t::convert_node_to_task(node * n) {
    // bool encode_all_variables = true;
    bool encode_all_variables = false;
    task_info & task = *m_ptask;
    // SASSERT(task.m_node_id == UINT32_MAX);
    task.m_node_id = n->id();
    task.m_depth = n->depth();
    vector<lit> temp_units;
    vector<vector<lit>> temp_clauses;
    // for (unsigned i = 0, isz = (*m_ptr_clauses).size(); i < isz; ++i) {
    //     clause * cla = (*m_ptr_clauses)[i];

    // for (unsigned i = 0, isz = m_clauses.size(); i < isz; ++i) {
    //     clause * cla = m_clauses[i];
    //     vector<lit> lit_cla;
    //     for (unsigned j = 0, jsz = cla->m_size; j < jsz; ++j) {
    //         atom * a = (*cla)[j];
    //         lit_cla.push_back(std::move(convert_atom_to_lit(a)));
    //     }
    //     task.m_clauses.push_back(lit_cla);
    // }
    // return false;

    for (unsigned i = 0, isz = m_clauses.size(); i < isz; ++i) {
        clause * cla = m_clauses[i];
        m_temp_atom_buffer.reset();
        bool skippable = false;
        for (unsigned j = 0, jsz = cla->m_size; j < jsz; ++j) {
            atom * a = (*cla)[j];
            lbool res = value(a, n);
            TRACE("linxi_subpaving",
                tout << "atom: ";
                display(tout, a);
                tout << "\n";
                tout << "bool: " << a->is_bool() << "\n";
                tout << "open: " << a->is_open() << "\n";
                tout << "lower: " << a->is_lower() << "\n";
                tout << "res: " << res << "\n";
            );
            if (res == l_true) {
                skippable = true;
                break;
            }
            else if (res == l_false) {
                continue;
            }
            else {
                m_temp_atom_buffer.push_back(a);
            }
        }
        if (skippable)
            continue;
        if (m_temp_atom_buffer.size() == 0) {
            {
                m_temp_stringstream << "UNSAT: empty clause in node: " << n->id();
                write_debug_ss_line_to_coordinator();
            }
            return true;
        }
        if (m_temp_atom_buffer.size() == 1) {
            temp_units.push_back(std::move(convert_atom_to_lit(m_temp_atom_buffer[0])));
            continue;
        }
        ++task.m_undef_clause_num;
        task.m_undef_lit_num += m_temp_atom_buffer.size();
        vector<lit> lit_cla, simp_lit_cla;
        for (unsigned j = 0, jsz = m_temp_atom_buffer.size(); j < jsz; ++j) {
            atom * a = m_temp_atom_buffer[j];
            lit_cla.push_back(std::move(convert_atom_to_lit(a)));
        }
        // temp_clauses.push_back(std::move(lit_cla));
        if (simplify_ineqs_in_clause(lit_cla, simp_lit_cla, false)) {
            ++m_skip_clause_cnt;
        }
        else {
            unsigned simp_sz = simp_lit_cla.size();
            assert(simp_sz > 0);
            if (simp_sz == 1) {
                temp_units.push_back(std::move(simp_lit_cla[0]));
            }
            else {
                temp_clauses.push_back(std::move(simp_lit_cla));
            }
            task.m_undef_lit_num += simp_lit_cla.size();
        }
    }
    
    remove_dominated_clauses(temp_clauses, task.m_clauses);
    
    if (!encode_all_variables) {
        for (unsigned i = 0, sz = m_unit_clauses.size(); i < sz; ++i) {
            atom * at = UNTAG(atom*, m_unit_clauses[i]);
            if (m_defs[at->m_x] == nullptr)
                continue;
            temp_units.push_back(std::move(convert_atom_to_lit(at)));
            // ++task.m_undef_clause_num;
            // ++task.m_undef_lit_num;
        }
    
        for (unsigned i = 0, sz = n->up_atoms().size(); i < sz; ++i) {
            atom * at = n->up_atoms()[i];
            if (m_defs[at->m_x] == nullptr)
                continue;
            temp_units.push_back(std::move(convert_atom_to_lit(at)));
            // ++task.m_undef_clause_num;
            // ++task.m_undef_lit_num;
        }
    }

    for (unsigned x = 0, sz = num_vars(); x < sz; ++x) {
        if (!encode_all_variables) {
            if (m_defs[x] != nullptr)
                continue;
        }
        if (m_is_bool[x]) {
            if (n->bvalue(x) == bvalue_kind::b_undef)
                continue;
            temp_units.push_back(lit());
            lit & l = temp_units.back();
            l.m_x = x;
            l.m_bool = true;
            l.m_open = false;
            if (n->bvalue(x) == b_false)
                l.m_lower = true;
            else if (n->bvalue(x) == b_true)
                l.m_lower = false;
            else
                UNREACHABLE();
        }
        else {
            // if (n->lower(x) == nullptr && n->upper(x) == nullptr)
            //     continue;
            bound * low = n->lower(x);
            bound * upp = n->upper(x);
            if (low != nullptr && upp != nullptr && nm().eq(low->value(), upp->value())) {
                temp_units.push_back(lit());
                lit & l = temp_units.back();
                l.m_x = x;
                l.m_bool = true;
                l.m_open = true;

                l.m_int = m_is_int[x];
                l.m_lower = false;
                l.m_val = &low->m_val;
            }
            else {
                if (low != nullptr) {
                    temp_units.push_back(lit());
                    lit & l = temp_units.back();
                    l.m_x = x;
                    l.m_bool = false;

                    l.m_int = m_is_int[x];
                    l.m_open = low->m_open;
                    l.m_lower = true;
                    l.m_val = &low->m_val;
                }
                if (upp != nullptr) {
                    temp_units.push_back(lit());
                    lit & l = temp_units.back();
                    l.m_x = x;
                    l.m_bool = false;

                    l.m_int = m_is_int[x];
                    l.m_open = upp->m_open;
                    l.m_lower = false;
                    l.m_val = &upp->m_val;
                }
            }
        }
    }
    if (temp_units.size() == 0)
        return false;
    // for (unsigned i = 0, sz = temp_units.size(); i < sz; ++i) {
    //     task.m_var_bounds.push_back(temp_units[i]);
    // }
    if (simplify_ineqs_in_clause(temp_units, task.m_var_bounds, true)) {
        {
            m_temp_stringstream << "UNSAT: conflict unit clauses in node: " << n->id();
            write_debug_ss_line_to_coordinator();
        }
        return true;
    }
    return false;
}

void context_t::collect_task_var_info() {
    task_info & task = *m_ptask;
    unsigned nv = num_vars();
    SASSERT(nv > 0);
    for (unsigned x = 0; x < nv; ++x) {
        m_var_max_deg[x] = 0;
        m_var_occs[x] = 0;
    }
    for (const vector<lit> & cla : task.m_clauses) {
        for (const lit & l : cla) {
            unsigned x = l.m_x;
            if (m_is_bool[x])
                continue;
            ++m_var_occs[x];
            definition * d = m_defs[x];
            if (d == nullptr) {
                if (m_var_max_deg[x] < 1)
                    m_var_max_deg[x] = 1;
            }
        }
    }
    for (const lit & l : task.m_var_bounds) {
        unsigned x = l.m_x;
        if (m_is_bool[x])
            continue;
        ++m_var_occs[x];
        definition * d = m_defs[x];
        if (d == nullptr) {
            if (m_var_max_deg[x] < 1)
                m_var_max_deg[x] = 1;
        }
    }
    for (int x = static_cast<int>(nv) - 1; x >= 0; --x) {
        definition * dx = m_defs[x];
        if (m_var_occs[x] == 0)
            continue;
        if (dx == nullptr)
            continue;
        if (dx->get_kind() == constraint::MONOMIAL) {
            monomial * m = get_monomial(x);
            for (unsigned i = 0, sz = m->size(); i < sz; ++i) {
                unsigned y = m->x(i);
                m_var_occs[y] += m_var_occs[x];
                if (m_var_max_deg[y] < m->degree(i))
                    m_var_max_deg[y] = m->degree(i);
            }
        }
        else if (dx->get_kind() == constraint::POLYNOMIAL) {
            polynomial * p = get_polynomial(x);
            for (unsigned i = 0, sz = p->size(); i < sz; ++i) {
                unsigned y = p->x(i);
                m_var_occs[y] += m_var_occs[x];
                definition * dy = m_defs[y];
                if (dy == nullptr) {
                    if (m_var_max_deg[y] < 1)
                        m_var_max_deg[y] = 1;
                }
                else if (dy->get_kind() == constraint::MONOMIAL) {
                    monomial * m = get_monomial(y);
                    for (unsigned j = 0, jsz = m->size(); j < jsz; ++j) {
                        unsigned z = m->x(j);
                        m_var_occs[z] += m_var_occs[y];
                        if (m_var_max_deg[z] < m->degree(j))
                            m_var_max_deg[z] = m->degree(j);
                    }
                }
                else {
                    UNREACHABLE();
                }
            }
        }
        else {
            UNREACHABLE();
        }
    }
}

void context_t::select_best_var(node * n) {
    collect_task_var_info();
    unsigned sz = m_var_split_candidates.size();
    if (sz == 0) {
        for (unsigned x = 0, nv = num_vars(); x < nv; ++x) {
            if (m_defs[x] != nullptr)
                continue;
            if (m_is_bool[x])
                continue;
            bound * l = n->lower(x);
            bound * u = n->upper(x);
            if (l != nullptr && u != nullptr 
             && nm().eq(l->value(), u->value())) {
                continue;
            }
            if (m_var_occs[x] == 0)
                continue;
            m_var_split_candidates.push_back(x);
        }
        sz = m_var_split_candidates.size();
        {
            m_temp_stringstream << "num var: " << num_vars() << ", candidate size: " << sz;
            write_debug_ss_line_to_coordinator();
        }
        if (sz == 0) {
            m_temp_stringstream << "partitioner error: no split candidate";
            write_debug_ss_line_to_coordinator();
        }
    }

    m_best_var_info.m_id = null_var;
    for (unsigned i = 0, x; i < sz; ++i) {
        x = m_var_split_candidates[i];
        bound * l = n->lower(x);
        bound * u = n->upper(x);
        if (l != nullptr && u != nullptr 
         && nm().eq(l->value(), u->value())) {
            continue;
        }
        if (m_var_occs[x] == 0)
            continue;
        unsigned split_cnt = m_var_unsolved_split_cnt[x];
        double avg_split_cnt = 
            static_cast<double>(split_cnt) / static_cast<double>(m_unsolved_task_num + 1);
        m_curr_var_info.m_id = x;
        m_curr_var_info.m_split_cnt = m_var_unsolved_split_cnt[x];
        m_curr_var_info.m_avg_split_cnt = avg_split_cnt;
        m_curr_var_info.m_cz = ((l == nullptr || nm().is_neg(l->value())) 
                             && (u == nullptr || nm().is_pos(u->value())));
        m_curr_var_info.m_deg = m_var_max_deg[x];
        m_curr_var_info.m_occ = m_var_occs[x];
        m_curr_var_info.m_is_too_short = false;
        numeral & width = m_curr_var_info.m_width;
        if (l == nullptr && u == nullptr) {
            nm().set(width, m_unbounded_penalty_sq);
            // unbouned: width = penalty ^ 2
            m_curr_var_info.m_width_score = 1.0;
        }
        else if (l == nullptr) {
            if (nm().is_neg(u->value())) {
                nm().set(width, u->value());
                nm().neg(width);
                if (nm().lt(width, 1))
                    nm().set(width, 1);
                nm().div(m_unbounded_penalty, width, width);
                // u < 0: penalty / max(1, -u)
            }
            else {
                nm().add(u->value(), m_unbounded_penalty, width);
                // u >= 0: penalty + u
            }
            m_curr_var_info.m_width_score = 0.95;
        }
        else if (u == nullptr) {
            if (nm().is_pos(l->value())) {
                nm().set(width, l->value());
                if (nm().lt(width, 1))
                    nm().set(width, 1);
                nm().div(m_unbounded_penalty, width, width);
                // l > 0: penalty / max(1, l)
            }
            else {
                nm().set(width, l->value());
                nm().neg(width);
                nm().add(width, m_unbounded_penalty, width);
                // l <= 0: penalty + -l
            }
            m_curr_var_info.m_width_score = 0.95;
        }
        else {
            nm().sub(u->value(), l->value(), width);
            m_curr_var_info.m_width_score = 0.9;
        }
        if (nm().le(width, m_small_value_thres)) {
            // m_curr_var_info.m_width_score = 0.9;
            m_curr_var_info.m_is_too_short = true;
        }
        m_curr_var_info.calc_score();
        if (m_best_var_info.m_id == null_var || m_curr_var_info < m_best_var_info) {
            m_best_var_info.copy(m_curr_var_info);
        }
    }
}

// return true for already unsat
bool context_t::update_node_state_unsat(unsigned id) {
    node_state & sta = m_nodes_state[id];
    if (sta == node_state::UNSAT)
        return true;
    if (sta == node_state::WAITING) {
        // {
        //     m_temp_stringstream << "node-" << id << " is unsat";
        //     write_debug_ss_line_to_coordinator();
        // }
        --m_alive_task_num;
    }
    // if (sta != node_state::UNCONVERTED) {
    //     node * n = m_nodes[id];
    //     --m_unsolved_task_num;
    //     for (unsigned i = 0, sz = n->depth(); i < sz; ++i) {
    //         --m_var_unsolved_split_cnt[n->split_vars()[i]];
    //     }
    // }
    node * n = m_nodes[id];
    --m_unsolved_task_num;
    for (unsigned i = 0, sz = n->depth(); i < sz; ++i) {
        --m_var_unsolved_split_cnt[n->split_vars()[i]];
    }
    sta = node_state::UNSAT;
    return false;
}

void context_t::unsat_push_down(node * n) {
    //#linxi TBD
    if (update_node_state_unsat(n->id()))
        return;
    node * ch = n->first_child();
    while (ch != nullptr) {
        unsat_push_down(ch);
        ch = ch->next_sibling();
    }
}

bool context_t::can_propagate_unsat(node * n) {
    node * ch = n->first_child();
    // if (ch == nullptr)
    //     return false;
    while (ch != nullptr) {
        if (m_nodes_state[ch->id()] != node_state::UNSAT)
            return false;
        ch = ch->next_sibling();
    }
    return true;
}

void context_t::unsat_push_up(node * n) {
    // SASSERT(m_nodes_state[id] != node_state::UNSAT);
    if (m_nodes_state[n->id()] == node_state::UNSAT)
        return;
    if (!can_propagate_unsat(n))
        return;
    update_node_state_unsat(n->id());
    node * parent = n->parent();
    if (parent != nullptr)
        unsat_push_up(parent);
}

void context_t::node_solved_unsat(node * n) {\
    if (update_node_state_unsat(n->id()))
        return;
    node * parent = n->parent();
    if (parent != nullptr)
        unsat_push_up(parent);
    node * ch = n->first_child();
    while (ch != nullptr) {
        unsat_push_down(ch);
        ch = ch->next_sibling();
    }
}

void context_t::parse_line(const std::string & line) {
    std::stringstream ss(line);
    int op_id;
    ss >> op_id;
    control_message::C2P op = control_message::C2P(op_id);
    if (op == control_message::C2P::unsat_node) {
        unsigned id;
        ss >> id;
        node_solved_unsat(m_nodes[id]);
    }
    else if (op == control_message::C2P::terminate_node) {
        unsigned id;
        ss >> id;
        if (m_nodes_state[id] == node_state::WAITING) {
            // {
            //     m_temp_stringstream << "node-" << id << " is terminated";
            //     write_debug_ss_line_to_coordinator();
            // }
            m_nodes_state[id] = node_state::TERMINATED;
            --m_alive_task_num;
        }
    }
    else {
        UNREACHABLE();
    }
}

void context_t::communicate_with_coordinator() {
    while (read_line_from_coordinator()) {
        write_debug_line_to_coordinator("read line from coordinator: " + m_current_line);
        parse_line(m_current_line);
        m_current_line = "";
        // {
        //     m_temp_stringstream << "alive tasks: "<< m_alive_task_num
        //         << "(" << m_max_alive_tasks << "), nodes: " << m_nodes.size();
        //     write_debug_ss_line_to_coordinator();
        // }
    }
}

/**
   \brief Select split node with the highest priority, which means:
    1. lowest depth
    2. most clauses
    3. most undecided literals
*/
typename context_t::node * context_t::select_next_node() {
    // return m_leaf_head; // filo
    // return m_leaf_tail; // fifo
    // if (m_leaf_heap.empty())
    //     return nullptr;
    // SASSERT(!m_leaf_heap.empty());
    // {
    //     const node_info & ni = m_leaf_heap.top();
    //     if (ni.m_id % (1 << 5) == 1) {
    //         m_temp_stringstream << "[leaf heap top] node-" << ni.m_id
    //             << ": depth=" << ni.m_depth << ", undef_clause_num=" <<ni.m_undef_clause_num
    //             << ", undef_lit_num=" << ni.m_undef_lit_num;
    //         if (ni.m_undef_clause_num > 0) {
    //             m_temp_stringstream
    //                 << ", avg_clause_length=" << static_cast<double>(ni.m_undef_lit_num) / static_cast<double>(ni.m_undef_clause_num);
    //         }
    //         write_debug_ss_line_to_coordinator();
    //     }
    // }
    unsigned nid = m_leaf_heap.top().m_id;
    m_leaf_heap.pop();
    return m_nodes[nid];
}

void context_t::split_node(node * n) {
    select_best_var(n);
    unsigned id = m_best_var_info.m_id;
    m_ptask->m_splitting_var = id;
    if (id == null_var) {
        write_debug_line_to_coordinator("no split var is selected");
        return;
    }
    write_debug_line_to_coordinator("best var: " + m_best_var_info.to_string());
    TRACE("linxi_subpaving", 
        var x = id;
        tout << "best var interval: " << x << "\n";
        bound * l = n->lower(x);
        bound * u = n->upper(x);
        if (l != nullptr) {
            display(tout, l);
            tout << " ";
        }
        if (u != nullptr) {
            display(tout, u);
        }
        if (l != nullptr || u != nullptr)
            tout << "\n";
    );
    node * left   = this->mk_node(n);
    node * right  = this->mk_node(n);
    
    // ++m_var_split_cnt[id];
    // m_var_split_prob[id] *= m_split_prob_decay;
    left->split_vars().push_back(id);
    right->split_vars().push_back(id);

    bool blower, bopen;
    // numeral & mid = m_tmp1;
    scoped_mpq mid(nm());

    vector<lit> x_lits;
    // vector<lit> x_lb_lits, x_ub_lits;
    for (const vector<lit> & cla : m_ptask->m_clauses) {
        for (const lit & l : cla) {
            // if (l.m_bool)
            //     continue;
            if (l.m_x != id)
                continue;
            if (l.is_eq_lit())
                continue;
            x_lits.push_back(l);
            // if (l.m_lower)
            //     x_lb_lits.push_back(l);
            // else
            //     x_ub_lits.push_back(l);
        }
    }

    unsigned x_lits_sz = x_lits.size();
    {
        m_temp_stringstream << "x_lits_sz: " << x_lits_sz;
        write_debug_ss_line_to_coordinator();
        
        m_temp_stringstream << "split var-"<< id;
        write_debug_ss_line_to_coordinator();

        bound * lb = n->lower(id);
        m_temp_stringstream << "x_lower: ";
        if (lb == nullptr) {
            m_temp_stringstream << "null";
        }
        else {
            display(m_temp_stringstream, lb);
        }
        write_debug_ss_line_to_coordinator();

        bound * ub = n->upper(id);
        m_temp_stringstream << "x_upper: ";
        if (ub == nullptr) {
            m_temp_stringstream << "null";
        }
        else {
            display(m_temp_stringstream, ub);
        }
        write_debug_ss_line_to_coordinator();
    }

    if (x_lits_sz > 0) {
    // if (false) {
        // {
        //     for (const lit & l : x_lits) {
        //         m_temp_stringstream << "(" << lit_to_string(l) << ") ";
        //     }
        //     write_debug_ss_line_to_coordinator();
        // }
        // std::sort(x_lits.begin(), x_lits.end(), arith_lit_lt(nm()));
        // {
        //     m_temp_stringstream << "sort done";
        //     write_debug_ss_line_to_coordinator();
        // }
        // {
        //     for (const lit & l : x_lits) {
        //         m_temp_stringstream << "(" << lit_to_string(l) << ") ";
        //     }
        //     write_debug_ss_line_to_coordinator();
        // }
        // vector<unsigned> suf(x_lits_sz + 1);
        // suf[x_lits_sz] = 0;
        // for (int i = x_lits_sz - 1; i >= 0; --i) {
        //     suf[i] = suf[i + 1];
        //     if (x_lits[i].m_lower)
        //         ++suf[i];
        // }
        // unsigned best_lit_id = 0, best_score = 0;
        // unsigned pre = 0;
        // for (unsigned i = 0; i < x_lits_sz; ++i) {
        //     if (!x_lits[i].m_lower)
        //         ++pre;
        //     unsigned score = suf[i] + pre;
        //     if (score > best_score) {
        //         best_score = score;
        //         best_lit_id = i;
        //     }
        // }
        // unsigned best_lit_id = 0, best_score = 0;
        // unsigned pre = 0;
        // for (unsigned i = 0; i < x_lits_sz; ++i) {
        //     if (!x_lits[i].m_lower)
        //         ++pre;
        //     unsigned score = suf[i] + pre;
        //     if (score > best_score) {
        //         best_score = score;
        //         best_lit_id = i;
        //     }
        // }
        // {
        //     m_temp_stringstream << "best_lit_id: " << best_lit_id
        //         << ", best_score: " << best_score;
        //     write_debug_ss_line_to_coordinator();
        // }
        unsigned random_id = 0;
        std::uniform_int_distribution<> dis(0, x_lits_sz - 1);
        random_id = dis(m_rand);
        lit & l = x_lits[random_id];
        // {
        //     m_temp_stringstream << "split lit(left child): " << lit_to_string(l);
        //     write_debug_ss_line_to_coordinator();
        // }
        // lit & l = x_lits[x_lits_sz >> 1];
        blower = static_cast<bool>(l.m_lower);
        bopen = static_cast<bool>(l.m_open);
        nm().set(mid, *l.m_val);
    }
    else {
        bound * lower = n->lower(id);
        bound * upper = n->upper(id);
        
        blower = false;
        bopen = false;
        // x <= mid, x > mid
        if (m_best_var_info.m_cz) {
            nm().set(mid, 0);
            // mid == 0
        }
        else if (lower == nullptr) {
            // (-oo, upper}
            SASSERT(upper != nullptr);
            nm().set(mid, upper->value());
            nm().floor(mid, mid);
            nm().sub(mid, m_split_delta, mid);
            // mid == upper - delta
        }
        else if (upper == nullptr) {
            SASSERT(lower != nullptr);
            nm().set(mid, lower->value());
            nm().ceil(mid, mid);
            nm().add(mid, m_split_delta, mid);
            // mid == lower + delta
        }
        else {
            numeral & two = m_tmp2;
            SASSERT(!nm().eq(lower->value(), upper->value()));
            nm().set(two, 2);
            nm().add(lower->value(), upper->value(), mid);
            nm().div(mid, two, mid);

            numeral & width = m_tmp3;
            nm().sub(upper->value(), lower->value(), width);
            if (nm().gt(width, 10))
                nm().ceil(mid, mid);
            
            if (!(nm().lt(lower->value(), mid) && nm().lt(mid, upper->value())))
                throw subpaving::exception();
            // mid == (lower + upper)/2
        }
    }
    // numeral & nmid = m_tmp2;
    scoped_mpq nmid(nm());
    bool nlower = blower, nopen = bopen;
    normalize_bound(id, mid, nmid, nlower, nopen);
    bound * lb = mk_bound(id, nmid, nlower, nopen, left, justification());
    {
        m_temp_stringstream << "left child bound: ";
        display(m_temp_stringstream, lb);
        write_debug_ss_line_to_coordinator();
    }

    lit & lc = m_ptask->m_split_left_child;
    lc.m_x = id;
    lc.m_bool = false;

    lc.m_int = m_is_int[id];
    lc.m_open = lb->m_open;
    lc.m_lower = lb->m_lower;
    lc.m_val = &(lb->m_val);

    nlower = !blower, nopen = !bopen;
    normalize_bound(id, mid, nmid, nlower, nopen);
    bound * rb = mk_bound(id, nmid, nlower, nopen, right, justification());
    // rb = mk_bound(id, nmid, blower, bopen, right, justification());
    {
        m_temp_stringstream << "right child bound: ";
        display(m_temp_stringstream, rb);
        write_debug_ss_line_to_coordinator();
    }

    lit & rc = m_ptask->m_split_right_child;
    rc.m_x = id;
    rc.m_bool = false;
    rc.m_int = m_is_int[id];
    rc.m_open = rb->m_open;
    rc.m_lower = rb->m_lower;
    rc.m_val = &(rb->m_val);
}

bool context_t::create_new_task() {
    TRACE("subpaving_stats", statistics st; collect_statistics(st); tout << "statistics:\n"; st.display_smt2(tout););
    TRACE("subpaving_main", display_params(tout););
    
    while (true) {
        if (m_leaf_heap.empty())
            break;
        node * n = select_next_node();
        TRACE("subpaving_main", tout << "selected node: #" << n->id() << ", depth: " << n->depth() << "\n";);
        if (n->inconsistent()) {
            m_nodes_state[n->id()] = node_state::UNSAT;
            continue;
        }
        if (m_nodes_state[n->id()] != node_state::UNCONVERTED)
            continue;
        if (n->parent() != nullptr && m_nodes_state[n->parent()->id()] == node_state::UNSAT) {
            m_nodes_state[n->id()] = node_state::UNSAT;
            continue;
        }
        TRACE("subpaving_main", tout << "node #" << n->id() << " after propagation\n";
                display_bounds(tout, n););
        
        m_conj_simplified_cnt = 0;
        m_disj_simplified_cnt = 0;
        m_skip_clause_cnt = 0;
        bool is_unsat = convert_node_to_task(n);
        if (!m_root_bicp_done) {
            m_root_bicp_done = true;
            {
                m_temp_stringstream << "root_bicp done";
                write_debug_ss_line_to_coordinator();
            }
        }
        if (is_unsat) {
            m_ptask->reset();
            node * pa = n->parent();
            int pid = -1;
            if (pa != nullptr)
                pid = static_cast<int>(pa->id());
            m_temp_stringstream << control_message::P2C::new_unsat_node 
                                << " " << n->id() << " " << pid;
            write_ss_line_to_coordinator();
            m_nodes_state[n->id()] = node_state::UNSAT;
            continue;
        }
        {
            // m_temp_stringstream << "alive tasks: "<< m_alive_task_num
            //     << "(" << m_max_alive_tasks << "), nodes: " << m_nodes.size();
            write_debug_ss_line_to_coordinator();
            if (m_disj_simplified_cnt > 0) {
                m_temp_stringstream << "node-" << n->id() << " m_disj_simplified_cnt (logic or): " << m_disj_simplified_cnt;
                write_debug_ss_line_to_coordinator();
            }
            if (m_conj_simplified_cnt > 0) {
                m_temp_stringstream << "node-" << n->id() << " m_conj_simplified_cnt (logic and): " << m_conj_simplified_cnt;
                write_debug_ss_line_to_coordinator();
            }
            if (m_skip_clause_cnt > 0) {
                m_temp_stringstream << "node-" << n->id() << " m_skip_clause_cnt: " << m_skip_clause_cnt;
                write_debug_ss_line_to_coordinator();
            }
        }
        return true;
    }
    return false;
}

// BICP and arithmetic partitioning start here
lbool context_t::operator()() {
    TRACE("linxi_subpaving", tout << "operator()\n");
    init_partition();
    init();
    if (m_root->inconsistent()) {
        // unsat
        return l_false;
    }
    propagate(m_root);
    if (m_root->inconsistent()) {
        // unsat
        return l_false;
    }
    // for (unsigned i = 0, sz = m_root->depth(); i < sz; ++i)
    //     ++m_var_unsolved_split_cnt[m_root->split_vars()[i]];
    // create_new_task();

    bool is_unsat = convert_node_to_task(m_root);
    if (is_unsat) {
        // unsat
        return l_false;
    }

    split_node(m_root);
    return l_true;
}

void context_t::display_bounds(std::ostream & out) const {
    ptr_vector<node> leaves;
    collect_leaves(leaves);
    typename ptr_vector<node>::const_iterator it  = leaves.begin();
    typename ptr_vector<node>::const_iterator end = leaves.end();
    for (bool first = true; it != end; ++it) {
        node * n = *it;
        if (first)
            first = false;
        else
            out << "=========\n";
        display_bounds(out, n);
    }
}

// -----------------------------------
//
// Statistics
//
// -----------------------------------

void context_t::reset_statistics() {
    m_num_conflicts = 0;
    m_num_mk_bounds = 0;
    m_num_splits    = 0;
    m_num_visited   = 0;
}

void context_t::collect_statistics(statistics & st) const {
    st.update("conflicts",  m_num_conflicts);
    st.update("new bounds", m_num_mk_bounds);
    st.update("splits",     m_num_splits);
    st.update("nodes",      m_num_nodes);
    st.update("visited",    m_num_visited);
}

// -----------------------------------
//
// Debugging support
//
// -----------------------------------

bool context_t::is_bound_of(bound * b, node * n) const {
    bound * c = n->trail_stack();
    while (c != nullptr) {
        if (c == b)
            return true;
        if (c->timestamp() <= b->timestamp())
            return false;
        c = c->prev();
    }
    return false;
}

bool context_t::check_leaf_dlist() const {
    node * n = m_leaf_head;
    while (n != nullptr) {
        node * next = n->next();
        SASSERT(next != 0 || m_leaf_tail  == n);
        SASSERT(next == 0 || next->prev() == n);
        n = next;
    }
    return true;
}

bool context_t::check_tree() const {
    ptr_buffer<node> todo;
    if (m_root != nullptr)
        todo.push_back(m_root);
    while (!todo.empty()) {
        node * n = todo.back();
        todo.pop_back();
        node * c = n->first_child();
        while (c != nullptr) {
            SASSERT(c->parent() == n);
            todo.push_back(c);
            c = c->next_sibling();
        }
    }
    return true;
}

bool context_t::check_invariant() const {
    SASSERT(check_tree());
    SASSERT(check_leaf_dlist());
    return true;
}


};
