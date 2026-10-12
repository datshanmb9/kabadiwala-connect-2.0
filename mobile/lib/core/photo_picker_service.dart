import 'package:image_picker/image_picker.dart';
import 'package:uuid/uuid.dart';

/// Thin wrapper around image_picker. Also owns the honest reference-id
/// scheme for a locally captured photo: the Phase 2 backend's
/// `POST /ewaste/submissions` endpoint only accepts an opaque
/// `photo_file_id` string — there is no file-upload/storage endpoint yet
/// — so we generate a clearly-local-only identifier rather than ever
/// claiming the image bytes were uploaded anywhere.
class PhotoPickerService {
  final ImagePicker _picker = ImagePicker();
  static const Uuid _uuid = Uuid();

  Future<XFile?> pickPhoto({required ImageSource source}) {
    return _picker.pickImage(source: source, maxWidth: 1600, imageQuality: 85);
  }

  static String localPhotoReference() => 'local-photo:${_uuid.v4()}';
}
