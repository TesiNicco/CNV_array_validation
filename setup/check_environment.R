# Run in a fresh R process after install_r_dependencies.R.
prefix <- Sys.getenv("CONDA_PREFIX")
if (!nzchar(prefix)) stop("Run this script through setup_environment.sh")
prefix <- normalizePath(prefix, mustWork = TRUE)
target_library <- normalizePath(file.path(R.home(), "library"), mustWork = TRUE)
if (!startsWith(target_library, paste0(prefix, "/"))) stop("Rscript is outside the mamba environment")
.libPaths(target_library, include.site = FALSE)
Sys.setenv(TORCH_HOME = file.path(target_library, "torch"))

packages <- c("data.table", "stringr", "BiocManager", "BiocParallel", "torch",
              "torchvision", "luz", "CNValidatron", "argparse", "remotes")
for (package in packages) {
    if (!requireNamespace(package, quietly = TRUE)) stop("Cannot load R package: ", package)
    cat(package, as.character(utils::packageVersion(package)), "OK\n")
}
if (!torch::torch_is_installed()) stop("Torch runtime is missing")
value <- as.numeric(torch::torch_sum(torch::torch_tensor(c(1, 2, 3), device = "cpu")))
if (!identical(value, 6)) stop("Torch CPU calculation failed")
cat("Torch CPU calculation OK: 1 + 2 + 3 = 6\n")
