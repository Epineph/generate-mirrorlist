#!/usr/bin/env Rscript
# Render the saved mirror evidence to Markdown and, optionally, A4 PDF.

# ---------------------------------------------------------------------------
# CLI and prerequisites
# ---------------------------------------------------------------------------

usage = function() {
  cat(paste0(
    "Usage: Rscript scripts/render-report.R [OPTIONS]\n\n",
    "  --markdown-only    Generate Markdown without the PDF.\n",
    "  --output-dir DIR   Destination directory (default: project docs/).\n",
    "  -h, --help         Show this help.\n\n",
    "Reads saved evidence only; no network requests or benchmarks run.\n",
    "Requires R packages rmarkdown, knitr and jsonlite, plus Pandoc.\n",
    "PDF output also requires XeLaTeX and its normal LaTeX packages.\n"
  ))
}

main = function() {
  script_arg = grep("^--file=", commandArgs(), value = TRUE)
  if (length(script_arg) != 1L) {
    stop("Run this script with Rscript.", call. = FALSE)
  }
  script = normalizePath(sub("^--file=", "", script_arg), mustWork = TRUE)
  project = dirname(dirname(script))
  output_dir = file.path(project, "docs")
  make_pdf = TRUE
  args = commandArgs(trailingOnly = TRUE)
  index = 1L
  while (index <= length(args)) {
    argument = args[[index]]
    if (argument %in% c("-h", "--help")) {
      usage()
      return(invisible(NULL))
    } else if (argument == "--markdown-only") {
      make_pdf = FALSE
    } else if (argument == "--output-dir") {
      index = index + 1L
      if (index > length(args) || !nzchar(args[[index]])) {
        stop("--output-dir requires a directory.", call. = FALSE)
      }
      output_dir = args[[index]]
    } else {
      stop("Unknown option: ", argument, " (see --help).", call. = FALSE)
    }
    index = index + 1L
  }

  packages = c("rmarkdown", "knitr", "jsonlite")
  missing = packages[!vapply(packages, requireNamespace, logical(1),
                            quietly = TRUE)]
  if (length(missing)) {
    stop("Missing R packages: ", paste(missing, collapse = ", "),
         ". Install them before rendering.", call. = FALSE)
  }
  if (!nzchar(Sys.which("pandoc"))) {
    stop("pandoc is required; install it before rendering.", call. = FALSE)
  }
  if (make_pdf && !nzchar(Sys.which("xelatex"))) {
    stop("xelatex is missing; install it or use --markdown-only.",
         call. = FALSE)
  }
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  output_dir = normalizePath(output_dir, mustWork = TRUE)
  source = file.path(project, "docs", "mirrorlist-summary.Rmd")
  markdown = file.path(output_dir, "mirrorlist-summary.md")
  pdf = file.path(output_dir, "mirrorlist-summary.pdf")
  intermediates = tempfile("mirror-report-")
  dir.create(intermediates)
  on.exit(unlink(intermediates, recursive = TRUE), add = TRUE)

  # Render once to Markdown so the PDF and Markdown share identical content.
  rmarkdown::render(
    input = source,
    output_format = rmarkdown::md_document(
      variant = "gfm", preserve_yaml = TRUE
    ),
    output_file = basename(markdown),
    output_dir = output_dir,
    intermediates_dir = intermediates,
    knit_root_dir = dirname(source),
    params = list(evidence_dir = file.path(project, "docs", "evidence")),
    envir = new.env(parent = globalenv()),
    quiet = TRUE,
    encoding = "UTF-8"
  )
  cat("Markdown: ", markdown, "\n", sep = "")

  if (make_pdf) {
    arguments = c(
      markdown, "--standalone", "--pdf-engine=xelatex",
      "-V", "papersize=a4", "-V", "geometry:margin=1.5cm",
      "-V", "fontsize=12pt", "-V", "mainfont=Noto Serif",
      "--syntax-highlighting=tango", "--output", pdf
    )
    status = system2(Sys.which("pandoc"), args = shQuote(arguments))
    if (status != 0L) {
      stop("PDF conversion failed; the Markdown report was retained.",
           call. = FALSE)
    }
    cat("PDF: ", pdf, "\n", sep = "")
  }
}

tryCatch(main(), error = function(error) {
  message("render-report: ", conditionMessage(error))
  quit(status = 1L)
})
