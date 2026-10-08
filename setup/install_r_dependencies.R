# Called through mamba run by setup_environment.sh. No user-library installation.
options(repos = c(CRAN = "https://cloud.r-project.org"), timeout = 1200)

prefix <- Sys.getenv("CONDA_PREFIX")
if (!nzchar(prefix)) stop("Run this script through setup_environment.sh")
prefix <- normalizePath(prefix, mustWork = TRUE)
target_library <- normalizePath(file.path(R.home(), "library"), mustWork = TRUE)
if (!startsWith(target_library, paste0(prefix, "/"))) {
    stop("Rscript is outside the selected mamba environment: ", R.home())
}
if (file.access(target_library, 2) != 0) stop("R library is not writable: ", target_library)
.libPaths(target_library, include.site = FALSE)

# The runtime was installed by install_torch_runtime.R in a separate process.
# Verify and load it normally before installing packages that depend on Torch.
Sys.setenv(TORCH_INSTALL = "0", TORCH_LOAD = "1", TORCH_VERIFY_LOAD = "TRUE",
           CUDA = "cpu", TORCH_HOME = file.path(target_library, "torch"))
for (package in c("remotes", "torch", "luz", "BiocParallel", "data.table", "stringr",
                  "argparse", "BiocManager", "ggplot2", "imager", "igraph")) {
    if (!requireNamespace(package, quietly = TRUE)) {
        stop("Missing conda dependency: ", package, ". Check the mamba environment update.")
    }
}

if (!torch::torch_is_installed()) stop("Torch runtime cannot load; inspect the error above")
if (as.numeric(torch::torch_sum(torch::torch_tensor(c(1, 2, 3), device = "cpu"))) != 6) {
    stop("Torch CPU calculation failed")
}

# Versions matching the tested analysis environment.
torchvision_version <- "0.6.0"
cnvalidatron_ref <- "c436bc0a69f19950e7357d9c0459af4950e97088"
installed_version <- if (requireNamespace("torchvision", quietly = TRUE)) {
    as.character(utils::packageVersion("torchvision"))
} else ""
if (installed_version != torchvision_version) {
    message("Installing torchvision ", torchvision_version)
    remotes::install_version("torchvision", version = torchvision_version,
                             lib = target_library, dependencies = NA,
                             upgrade = "never", build_vignettes = FALSE)
}

description <- if (length(find.package("CNValidatron", quiet = TRUE)) > 0) {
    utils::packageDescription("CNValidatron")
} else NULL
installed_ref <- if (!is.null(description)) description$RemoteSha else NULL
if (is.null(installed_ref) || installed_ref != cnvalidatron_ref) {
    message("Installing CNValidatron at the pinned commit: ", cnvalidatron_ref)
    # All hard dependencies are provided by mamba and torchvision above.
    remotes::install_github("SinomeM/CNValidatron_fl", ref = cnvalidatron_ref,
                            lib = target_library, dependencies = FALSE,
                            upgrade = "never", build_vignettes = FALSE)
}
if (!requireNamespace("torchvision", quietly = TRUE) ||
    !requireNamespace("CNValidatron", quietly = TRUE)) {
    stop("R package installation did not complete; inspect installation errors above")
}
if (as.character(utils::packageVersion("torchvision")) != torchvision_version) {
    stop("torchvision is not installed at the requested version")
}
description <- utils::packageDescription("CNValidatron")
if (!identical(description$RemoteSha, cnvalidatron_ref)) {
    stop("CNValidatron is not installed at the requested pinned commit")
}
message("R dependencies installed in ", target_library)
