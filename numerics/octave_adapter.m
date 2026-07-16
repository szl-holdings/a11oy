% SPDX-License-Identifier: Apache-2.0
% Fixed, data-only GNU Octave adapter. No eval/source/pkg/system/network calls.

args = argv();
if numel(args) != 2
  error("a11oy:numerics:arguments", "expected fixed input and output paths");
endif

input_path = args{1};
output_path = args{2};
request = jsondecode(fileread(input_path));
operation = request.operation;
matrix = request.inputs.matrix;

if strcmp(operation, "MATRIX_SOLVE") || strcmp(operation, "VALIDATE_REFERENCE_VECTOR")
  values = matrix \ request.inputs.rhs(:);
elseif strcmp(operation, "SYMMETRIC_EIGENVALUES")
  values = sort(eig(matrix));
else
  error("a11oy:numerics:operation", "unsupported fixed operation");
endif

response = struct(
  "schema", "szl.numerics.engine-response/v1",
  "state", "RESULT",
  "operation", operation,
  "values", reshape(values, 1, []),
  "substrate_evidence", "UNKNOWN"
);

handle = fopen(output_path, "w");
if handle < 0
  error("a11oy:numerics:output", "cannot open fixed output path");
endif
fprintf(handle, "%s", jsonencode(response));
fclose(handle);
