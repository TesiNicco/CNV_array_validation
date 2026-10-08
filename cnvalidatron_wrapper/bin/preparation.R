#!/usr/bin/env Rscript
# Convert supported named-column inputs and create validation signal indexes.
script <- normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1]), mustWork = TRUE)
source(file.path(dirname(script), "wrapper_common.R"))

signal_table <- function(path) {
    dt <- fread(path, sep = "\t")
    find_column <- function(name, required = TRUE) {
        matches <- names(dt)[names(dt) == name | endsWith(names(dt), paste0(".", name))]
        if (length(matches) > 1 || (required && !length(matches))) stop(path, ": expected one column named ", name)
        if (length(matches)) matches else NULL
    }
    chrom <- find_column("Chr")
    position <- if ("Start" %in% names(dt)) "Start" else find_column("Position")
    lrr <- find_column("Log R Ratio")
    baf <- find_column("B Allele Freq")
    adjusted <- find_column("Log R Ratio Adjusted", required = FALSE)
    start <- positive_integer(dt[[position]], paste(path, "position"))
    chr <- positive_integer(sub("^chr", "", as.character(dt[[chrom]])), paste(path, "chromosome"))
    end <- if ("End" %in% names(dt)) positive_integer(dt$End, paste(path, "end")) else start
    numeric_signal <- function(name) {
        x <- suppressWarnings(as.numeric(dt[[name]]))
        if (anyNA(x) || any(!is.finite(x))) stop(path, ": nonnumeric/missing/nonfinite values in ", name)
        x
    }
    lrr_values <- numeric_signal(lrr)
    baf_values <- numeric_signal(baf)
    if (any(baf_values < 0 | baf_values > 1)) stop(path, ": BAF outside [0, 1]")
    if (any(end < start)) stop(path, ": end precedes start")
    result <- data.table(Chr = chr, Start = start, End = end,
        `Log R Ratio` = lrr_values, `B Allele Freq` = baf_values,
        `Log R Ratio Adjusted` = if (!is.null(adjusted)) numeric_signal(adjusted) else lrr_values)
    if (!nrow(result)) stop(path, ": signal table is empty")
    if (anyDuplicated(result[, .(Chr, Start)])) stop(path, ": duplicate signal positions")
    setorder(result, Chr, Start)
    result
}

penncnv_table <- function(path, samples) {
    lines <- readLines(path, warn = FALSE)
    lines <- lines[nzchar(trimws(lines))]
    if (!length(lines)) return(data.table(sample_ID = character(), chr = integer(), start = integer(), end = integer(), GT = integer(), CN = integer(), numsnp = integer()))
    records <- lapply(lines, function(line) {
        fields <- strsplit(trimws(line), "[[:space:]]+")[[1]]
        if (length(fields) < 5 || !grepl("^chr[0-9]+:[0-9]+-[0-9]+$", fields[1]) ||
            !grepl("^numsnp=[0-9]+$", fields[2]) || !grepl("(^|,)cn=[0-9]+(,|$)", fields[4])) stop("Invalid PennCNV record: ", line)
        source <- input_path(fields[5], dirname(path))
        ix <- match(source, samples$file_path)
        if (is.na(ix)) stop("CNV signal path does not match the sample manifest: ", fields[5])
        locus <- strsplit(sub("^chr", "", fields[1]), "[:-]")[[1]]
        cn <- as.numeric(sub(".*(?:^|,)cn=([0-9]+)(?:,.*)?$", "\\1", fields[4], perl = TRUE))
        data.table(sample_ID = samples$sample_ID[ix], chr = locus[1], start = locus[2], end = locus[3],
            GT = if (cn %in% c(0, 1)) 1 else 2, CN = cn, numsnp = sub("^numsnp=", "", fields[2]))
    })
    rbindlist(records)
}

main <- function() {
    parser <- ArgumentParser(description = "Prepare named-column signals and CNV tables for CNValidatron; no wave correction or liftover")
    for (name in c("samples", "snps", "cnvs", "outdir")) parser$add_argument(paste0("--", name), required = TRUE)
    parser$add_argument("--cnv-format", choices = c("table", "penncnv"), required = TRUE,
        help = "Explicitly select a headered validation TSV or raw PennCNV calls")
    parser$add_argument("--check", action = "store_true", help = "Read/validate inputs without writing outputs")
    args <- parser$parse_args()
    sample_path <- input_path(args$samples)
    snps <- read_snps(input_path(args$snps))
    samples <- read_samples(sample_path)
    cnv_path <- input_path(args$cnvs)
    cnvs <- if (args$cnv_format == "table") read_cnvs(cnv_path, samples) else check_cnvs(penncnv_table(cnv_path, samples), samples)
    out <- new_output(args$outdir)
    for (tool in c("bgzip", "tabix")) if (!nzchar(Sys.which(tool))) stop("Executable missing: ", tool)
    for (path in samples$file_path) invisible(signal_table(path))
    if (args$check) { cat("Preparation preflight passed; no outputs written.\n"); return(invisible(NULL)) }
    if (!dir.create(out, recursive = TRUE)) stop("Cannot create output directory: ", out)
    out <- normalizePath(out)
    signals <- file.path(out, "signals")
    dir.create(signals)
    samples[, file_path_tabix := NA_character_]
    log <- file.path(out, "preparation.log")
    for (i in seq_len(nrow(samples))) {
        raw <- file.path(signals, paste0(samples$sample_ID[i], ".tsv"))
        write_table(signal_table(samples$file_path[i]), raw)
        zipped <- paste0(raw, ".gz")
        status <- system2(Sys.which("bgzip"), c("-c", shQuote(raw)), stdout = zipped, stderr = log)
        if (status != 0) stop("bgzip failed; see ", log)
        status <- system2(Sys.which("tabix"), c("-S", "1", "-s", "1", "-b", "2", "-e", "3", shQuote(zipped)), stdout = log, stderr = log)
        if (status != 0 || !file.exists(paste0(zipped, ".tbi"))) stop("tabix failed; see ", log)
        samples$file_path[i] <- raw
        samples$file_path_tabix[i] <- zipped
    }
    write_table(samples, file.path(out, "samples.tsv"))
    write_table(snps, file.path(out, "snps.tsv"))
    write_table(cnvs, file.path(out, "cnvs.tsv"))
    cat("Prepared inputs:", out, "\n")
    cat("Existing adjusted LRR is preserved; otherwise selected LRR is copied. No wave correction was performed.\n")
}
tryCatch(main(), error = function(e) { message("ERROR: ", conditionMessage(e)); quit(status = 1) })
