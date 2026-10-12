import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../features/auth/auth_controller.dart';
import '../features/home_user/home_user_repository.dart';
import '../features/home_user/models/home_user_profile.dart';
import '../features/translation/translation_text.dart';

class EditProfileScreen extends StatefulWidget {
  final HomeUserProfile profile;

  const EditProfileScreen({super.key, required this.profile});

  @override
  State<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends State<EditProfileScreen> {
  late final TextEditingController _nameController;
  late final TextEditingController _addressController;
  final _formKey = GlobalKey<FormState>();
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.profile.fullName);
    _addressController = TextEditingController(text: widget.profile.address);
  }

  @override
  void dispose() {
    _nameController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final updated = await context.read<HomeUserRepository>().updateProfile(
        accessToken: token,
        fullName: _nameController.text.trim(),
        address: _addressController.text.trim(),
      );
      if (!mounted) return;
      Navigator.of(context).pop(updated);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = context.tr('Could not save your profile.');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Edit Profile'))),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Text(context.tr(_error!), style: const TextStyle(color: Colors.red)),
              ),
            TextFormField(
              key: const Key('profile_name_field'),
              controller: _nameController,
              textCapitalization: TextCapitalization.words,
              decoration: InputDecoration(labelText: context.tr('Name')),
              validator: (value) => value == null || value.trim().isEmpty
                  ? context.tr('Please enter your name.')
                  : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              key: const Key('profile_address_field'),
              controller: _addressController,
              maxLines: 3,
              decoration: InputDecoration(labelText: context.tr('Address')),
              validator: (value) => value == null || value.trim().isEmpty
                  ? context.tr('Please enter your address.')
                  : null,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              key: const Key('save_profile_button'),
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Text(context.tr('Save')),
            ),
            const SizedBox(height: 8),
            OutlinedButton(
              key: const Key('cancel_profile_button'),
              onPressed: _saving ? null : () => Navigator.of(context).pop(),
              child: Text(context.tr('Cancel')),
            ),
          ],
        ),
      ),
    );
  }
}
