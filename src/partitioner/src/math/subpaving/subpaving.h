/*++
Copyright (c) 2012 Microsoft Corporation

Module Name:

    subpaving.h

Abstract:

    Subpaving for non-linear arithmetic.
    This is a wrapper for the different implementations
    of the subpaving module.
    This wrapper is the main interface between Z3 other modules and subpaving.
    Thus, it assumes that polynomials have precise integer coefficients, and
    bounds are rationals. If a particular implementation uses floats, then
    internally the bounds are approximated.
    
Author:

    Leonardo de Moura (leonardo) 2012-08-07.

Revision History:

--*/
#pragma once

#include "util/mpq.h"
#include "math/subpaving/subpaving_types.h"
#include "util/params.h"
#include "util/statistics.h"
#include "util/lbool.h"

namespace subpaving {

class context {
public:
    virtual ~context() = default;

    virtual unsynch_mpq_manager & qm() const = 0;

    /**
       \brief Return the number of variables in this subpaving object.
    */
    virtual unsigned num_vars() const = 0;
    
    /**
       \brief Create a new variable.
    */
    virtual var mk_var(bool is_int) = 0;
    virtual var mk_bvar() = 0;

    /**
       \brief Return true if \c x is an integer variable.
    */
    virtual bool is_int(var x) const = 0;
    
    /**
       \brief Create the monomial xs[0]^ks[0] * ... * xs[sz-1]^ks[sz-1].
       The result is a variable y s.t. y = xs[0]^ks[0] * ... * xs[sz-1]^ks[sz-1].
       
       \pre for all i \in [0, sz-1] : ks[i] > 0
       \pre sz > 0
    */
    virtual var mk_monomial(unsigned sz, power const * pws) = 0;
    
    /**
     * linxi updated, remove constant c
       \brief Create the sum as[0]*xs[0] + ... + as[sz-1]*xs[sz-1].
       The result is a variable y s.t. y = as[0]*xs[0] + ... + as[sz-1]*xs[sz-1].
       
       \pre sz > 0
       \pre for all i \in [0, sz-1] : as[i] != 0
    */
    virtual var mk_sum(unsigned sz, mpz const * as, var const * xs) = 0;

    /**
       \brief Create an atom.
    */
    virtual atom * mk_bool_atom(var x, bool neg) = 0;
    virtual atom * mk_eq_atom(var x, mpq const & k, bool neg) = 0;
    virtual atom * mk_ineq_atom(var x, mpq const & k, bool lower, bool open) = 0;
    virtual void inc_ref(atom * a) = 0;
    virtual void dec_ref(atom * a) = 0;

    /**
       \brief Assert the clause atoms[0] \/ ... \/ atoms[sz-1]
       \pre sz >= 1
    */
    virtual void add_clause(unsigned sz, atom * const * atoms) = 0;
    
    /**
       \brief Display constraints asserted in the subpaving.
    */
    virtual void display_constraints(std::ostream & out, bool use_star = false) const = 0;


    virtual void collect_param_descrs(param_descrs & r) = 0;

    virtual void updt_params(params_ref const & p) = 0;

    virtual void set_task_ptr(task_info * p) = 0;
    
    virtual void set_display_proc(display_var_proc * p) = 0;

    virtual void reset_statistics() = 0;

    virtual void collect_statistics(statistics & st) const = 0;

    virtual lbool operator()() = 0;

    virtual void display_bounds(std::ostream & out) const = 0;
};

context * mk_mpq_context(reslimit& lim, unsynch_mpq_manager & m, params_ref const & p = params_ref(), small_object_allocator * a = nullptr);

};


