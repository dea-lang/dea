/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include <Python.h>

typedef struct TSLanguage TSLanguage;

/* Return the Dea grammar's immutable Tree-sitter language descriptor. */
TSLanguage *tree_sitter_dea(void);

/**
 * Return a Python capsule referencing the immutable Dea language descriptor.
 *
 * The capsule does not own or destroy the static Tree-sitter descriptor.
 *
 * @param self Unused module receiver.
 * @param args Unused positional argument tuple.
 * @return New capsule reference, or NULL with a Python exception on allocation failure.
 */
static PyObject* _binding_language(PyObject *Py_UNUSED(self), PyObject *Py_UNUSED(args)) {
    return PyCapsule_New(tree_sitter_dea(), "tree_sitter.Language", NULL);
}

static struct PyModuleDef_Slot slots[] = {
#ifdef Py_GIL_DISABLED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static PyMethodDef methods[] = {
    {"language", _binding_language, METH_NOARGS,
     "Get the tree-sitter language for this grammar."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "_binding",
    .m_doc = NULL,
    .m_size = 0,
    .m_methods = methods,
    .m_slots = slots,
};

/**
 * Return the module definition for Python's multiphase initialization.
 *
 * Python initializes the static definition and manages the resulting module's lifetime.
 * This entry point does not allocate a separate module instance.
 *
 * @return Initialized static module definition for the import machinery.
 */
PyMODINIT_FUNC PyInit__binding(void) {
    return PyModuleDef_Init(&module);
}
