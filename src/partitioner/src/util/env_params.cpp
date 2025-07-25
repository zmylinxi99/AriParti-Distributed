/*++
Copyright (c) 2011 Microsoft Corporation

Module Name:

    env_params.cpp

Abstract:

    Goodies for updating environment parameters.

Author:

    Leonardo (leonardo) 2012-12-01

Notes:

--*/
#include "util/env_params.h"
#include "util/params.h"
#include "util/gparams.h"
#include "util/util.h"
#include "util/memory_manager.h"

void env_params::updt_params() {
    params_ref const& p = gparams::get_ref();
    set_verbosity_level(p.get_uint("verbose", get_verbosity_level()));
    enable_warning_messages(p.get_bool("warning", true));
    memory::set_max_size(megabytes_to_bytes(p.get_uint("memory_max_size", 0)));
    memory::set_max_alloc_count(p.get_uint("memory_max_alloc_count", 0));
    memory::set_high_watermark(p.get_uint("memory_high_watermark", 0));
    unsigned mb = p.get_uint("memory_high_watermark_mb", 0);
    if (mb > 0)
        memory::set_high_watermark(megabytes_to_bytes(mb));    
}

void env_params::collect_param_descrs(param_descrs & d) {
    d.insert("verbose", CPK_UINT, "be verbose, where the value is the verbosity level", "0");
    d.insert("warning", CPK_BOOL, "enable/disable warning messages", "true");
    d.insert("memory_max_size", CPK_UINT, "set hard upper limit for memory consumption (in megabytes), if 0 then there is no limit", "0");
    d.insert("memory_max_alloc_count", CPK_UINT, "set hard upper limit for memory allocations, if 0 then there is no limit", "0");
    d.insert("memory_high_watermark", CPK_UINT, "set high watermark for memory consumption (in bytes), if 0 then there is no limit", "0");
    d.insert("memory_high_watermark_mb", CPK_UINT, "set high watermark for memory consumption (in megabytes), if 0 then there is no limit", "0");

    d.insert("output_dir", CPK_STRING, "AriParti output dir", "ERROR");
    d.insert("partition_max_running_tasks", CPK_UINT, "AriParti maximum number of tasks running simultaneously", "32");
    d.insert("partition_rand_seed", CPK_UINT, "AriParti random seed", "0");
    d.insert("get_model_flag", CPK_UINT, "AriParti get model flag", "0");
}
