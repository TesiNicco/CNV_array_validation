# Shared input checks for the preparation and parallel-validation commands.
suppressPackageStartupMessages({ library(data.table); library(argparse) })

input_path <- function(path, base = getwd()) {
    path <- path.expand(path)
    if (!grepl("^/", path)) path <- file.path(base, path)
    normalizePath(path, mustWork = TRUE)
}

new_output <- function(path) {
    path <- path.expand(path)
    if (!grepl("^/", path)) path <- file.path(getwd(), path)
    if (grepl("[[:space:]]", path)) stop("Output paths must not contain whitespace: CNValidatron builds tabix commands from signal paths")
    if (file.exists(path) || dir.exists(path)) stop("Choose a NEW output directory: ", path)
    path
}

columns <- function(dt, required, label) {
    missing <- setdiff(required, names(dt))
    if (length(missing)) stop(label, " missing columns: ", paste(missing, collapse = ", "))
}

positive_integer <- function(x, label, allow_zero = FALSE) {
    y <- suppressWarnings(as.numeric(x))
    minimum <- if (allow_zero) 0 else 1
    if (anyNA(y) || any(!is.finite(y) | y < minimum | y != floor(y))) {
        stop(label, " must contain ", if (allow_zero) "nonnegative" else "positive", " integers")
    }
    y
}

read_samples <- function(path, indexed = FALSE) {
    dt <- fread(path, sep = "\t", colClasses = "character")
    required <- c("sample_ID", "file_path", if (indexed) "file_path_tabix")
    columns(dt, required, "Sample table")
    if (!nrow(dt)) stop("Sample table is empty")
    if (anyNA(dt$sample_ID) || any(!grepl("^[A-Za-z0-9-]+$", dt$sample_ID))) {
        stop("Sample IDs must use letters, digits and hyphens only")
    }
    if (anyDuplicated(dt$sample_ID)) stop("Duplicate sample IDs")
    dt$file_path <- vapply(dt$file_path, input_path, character(1), base = dirname(path))
    if (anyDuplicated(dt$file_path)) stop("Signal file listed more than once")
    if (indexed) {
        dt$file_path_tabix <- vapply(dt$file_path_tabix, input_path, character(1), base = dirname(path))
        if (any(grepl("[[:space:]]", dt$file_path_tabix))) stop("Indexed signal paths must not contain whitespace: CNValidatron builds tabix commands from them")
        invisible(lapply(paste0(dt$file_path_tabix, ".tbi"), input_path))
    }
    dt
}

read_snps <- function(path) {
    dt <- fread(path, sep = "\t", colClasses = "character")
    columns(dt, c("Name", "Chr", "Position"), "SNP table")
    if (!nrow(dt) || anyNA(dt$Name) || any(dt$Name == "")) stop("SNP table has no usable probe names")
    dt[, Chr := positive_integer(sub("^chr", "", Chr), "SNP chromosome")]
    dt[, Position := positive_integer(Position, "SNP position")]
    if ("Index" %in% names(dt)) dt[, Index := NULL]
    dt
}

check_cnvs <- function(dt, samples) {
    columns(dt, c("sample_ID", "chr", "start", "end", "GT", "CN", "numsnp"), "CNV table")
    if (anyNA(dt$sample_ID) || any(!dt$sample_ID %in% samples$sample_ID)) stop("CNV sample ID not present in sample table")
    dt[, chr := positive_integer(sub("^chr", "", as.character(chr)), "CNV chromosome")]
    dt[, start := positive_integer(start, "CNV start")]
    dt[, end := positive_integer(end, "CNV end")]
    dt[, numsnp := positive_integer(numsnp, "CNV SNP count")]
    dt[, CN := positive_integer(CN, "Copy number", allow_zero = TRUE)]
    dt[, GT := positive_integer(GT, "CNV genotype")]
    if (any(dt$end < dt$start)) stop("CNV end precedes start")
    expected_gt <- ifelse(dt$CN %in% c(0, 1), 1, 2)
    if (any(dt$GT != expected_gt) || any(dt$CN == 2)) stop("GT/CN must describe a deletion (GT 1, CN 0/1) or duplication (GT 2, CN >2)")
    dt[, chrom := chr]
    dt
}

read_cnvs <- function(path, samples) {
    check_cnvs(fread(path, sep = "\t", colClasses = list(character = "sample_ID")), samples)
}

write_table <- function(dt, path) fwrite(dt, path, sep = "\t", quote = FALSE, na = "NA")

empty_predictions <- function() {
    data.table(sample_ID = character(), start = numeric(), pred = integer(),
        pred_prob = numeric(), p_false = numeric(), p_true_del = numeric(),
        p_true_dup = numeric(), real_numsnp = integer(), chr = numeric(),
        end = numeric(), numsnp = integer(), GT = integer(), CN = integer())
}
