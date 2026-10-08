#!/usr/bin/env Rscript
# Launch independent validation workers and check their exit status.
script <- normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1]), mustWork = TRUE)
source(file.path(dirname(script), "wrapper_common.R"))

main <- function() {
    parser <- ArgumentParser(description = "Validate prepared CNVs in parallel R processes")
    for (name in c("samples", "snps", "cnvs", "model", "outdir")) parser$add_argument(paste0("--", name), required = TRUE)
    parser$add_argument("--workers", type = "integer", default = 1L, help = "Maximum concurrent R workers (default: 1)")
    parser$add_argument("--worker-script", default = file.path(dirname(script), "validation_CNV.r"), help = "Validation worker; normally use the bundled default")
    parser$add_argument("--check", action = "store_true", help = "Validate tables and file/index existence without starting workers")
    args <- parser$parse_args()
    if (is.na(args$workers) || args$workers < 1L) stop("--workers must be a positive integer")
    samples <- read_samples(input_path(args$samples), indexed = TRUE)
    snps <- read_snps(input_path(args$snps))
    cnvs <- read_cnvs(input_path(args$cnvs), samples)
    model <- input_path(args$model)
    worker <- input_path(args$worker_script)
    out <- new_output(args$outdir)
    if (args$check) { cat("Validation preflight passed; no outputs written. Model not loaded.\n"); return(invisible(NULL)) }
    if (!dir.create(out, recursive = TRUE)) stop("Cannot create output directory: ", out)
    out <- normalizePath(out)
    write_table(snps, file.path(out, "snps.tsv"))
    write_table(cnvs, file.path(out, "cnvs.tsv"))
    # Skip samples without calls, cap the worker count to avoid empty batches.
    samples <- samples[sample_ID %in% cnvs$sample_ID]
    if (!nrow(samples)) {
        write_table(empty_predictions(), file.path(out, "final_predictions.txt"))
        cat("No CNVs; wrote a header-only predictions file.\n")
        return(invisible(NULL))
    }
    workers <- min(args$workers, nrow(samples))
    samples[, worker_batch := rep(seq_len(workers), length.out = .N)]
    jobs <- lapply(seq_len(workers), function(i) {
        directory <- file.path(out, paste0("batch_", i))
        dir.create(directory)
        write_table(samples[worker_batch == i, setdiff(names(samples), "worker_batch"), with = FALSE], file.path(directory, "samples.tsv"))
        list(batch = i, directory = directory)
    })
    Sys.setenv(OMP_NUM_THREADS = "1", MKL_NUM_THREADS = "1", OPENBLAS_NUM_THREADS = "1")
    setDTthreads(1L)
    rscript <- file.path(R.home("bin"), "Rscript")
    invoke <- function(job) {
        log <- file.path(job$directory, "worker.log")
        command <- c(worker, "--batch", as.character(job$batch), "--snps", file.path(out, "snps.tsv"),
            "--cnvs", file.path(out, "cnvs.tsv"), "--samples", file.path(job$directory, "samples.tsv"),
            "--model", model, "--outdir", job$directory)
        status <- tryCatch(system2(rscript, shQuote(command), stdout = log, stderr = log, wait = TRUE),
            error = function(e) { writeLines(conditionMessage(e), log); 1L })
        list(status = status, log = log, prediction = file.path(job$directory, "predictions.txt"))
    }
    cat("Running", workers, "validation workers\n")
    results <- parallel::mclapply(jobs, invoke, mc.cores = workers, mc.preschedule = FALSE)
    failed <- vapply(results, function(result) inherits(result, "try-error") || is.null(result$status) || result$status != 0L, logical(1))
    if (any(failed)) {
        logs <- vapply(jobs[failed], function(job) file.path(job$directory, "worker.log"), character(1))
        stop("Validation worker failed; see ", paste(logs, collapse = ", "))
    }
    for (result in results) if (!file.exists(result$prediction)) stop("Worker exited without predictions: ", result$log)
    predictions <- lapply(results, function(result) fread(result$prediction, sep = "\t", colClasses = list(character = "sample_ID")))
    write_table(rbindlist(predictions), file.path(out, "final_predictions.txt"))
    cat("Finished:", file.path(out, "final_predictions.txt"), "\n")
}
tryCatch(main(), error = function(e) { message("ERROR: ", conditionMessage(e)); quit(status = 1) })
