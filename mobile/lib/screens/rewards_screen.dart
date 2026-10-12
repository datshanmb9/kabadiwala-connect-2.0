import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../core/idempotency_key_generator.dart';
import '../features/auth/auth_controller.dart';
import '../features/rewards/models/reward.dart';
import '../features/rewards/rewards_repository.dart';
import '../features/translation/translation_text.dart';
import '../shared/state_views.dart';

class RewardsScreen extends StatefulWidget {
  const RewardsScreen({super.key});

  @override
  State<RewardsScreen> createState() => _RewardsScreenState();
}

class _RewardsScreenState extends State<RewardsScreen> {
  bool _loading = true;
  String? _error;
  List<Reward> _rewards = [];
  String? _actioningRewardId;
  String? _actionError;
  final Map<String, String> _pendingRedeemKeys = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      final rewards = await context.read<RewardsRepository>().listMyRewards(token);
      if (!mounted) return;
      setState(() {
        _rewards = rewards;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  Future<void> _redeem(Reward reward) async {
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    setState(() {
      _actioningRewardId = reward.rewardId;
      _actionError = null;
    });
    final key = _pendingRedeemKeys[reward.rewardId] ?? IdempotencyKeyGenerator.generate();
    _pendingRedeemKeys[reward.rewardId] = key;
    try {
      final txn = await context.read<RewardsRepository>().redeem(
            rewardId: reward.rewardId,
            accessToken: token,
            idempotencyKey: key,
          );
      _pendingRedeemKeys.remove(reward.rewardId);
      if (!mounted) return;
      if (!txn.succeeded) {
        setState(() => _actionError = 'Redemption did not succeed this time — you may retry.');
      }
      await _load();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _actionError = e.message);
    } finally {
      if (mounted) setState(() => _actioningRewardId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.tr('My Rewards'))),
      body: RefreshIndicator(onRefresh: _load, child: _buildBody()),
    );
  }

  Widget _buildBody() {
    if (_loading) return const LoadingView(message: 'Loading your rewards…');
    if (_error != null) {
      return ListView(
        children: [const SizedBox(height: 80), ErrorView(message: _error!, onRetry: _load)],
      );
    }
    if (_rewards.isEmpty) {
      return ListView(
        children: [
          const SizedBox(height: 80),
          EmptyView(
            message: context.tr('No rewards computed yet. Rewards are credited monthly for e-waste you have contributed.'),
            icon: Icons.card_giftcard_outlined,
          ),
        ],
      );
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (_actionError != null) ...[
          InlineErrorBanner(message: _actionError!),
        ],
        ..._rewards.map((r) => _RewardCard(
              reward: r,
              actioning: _actioningRewardId == r.rewardId,
              onRedeem: () => _redeem(r),
            )),
      ],
    );
  }
}

class _RewardCard extends StatelessWidget {
  final Reward reward;
  final bool actioning;
  final VoidCallback onRedeem;

  const _RewardCard({required this.reward, required this.actioning, required this.onRedeem});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${context.tr('Period:')} ${reward.period}', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            Text('${context.tr('Points:')} ${reward.points}'),
            Text('${context.tr('Amount:')} ₹${reward.amount}'),
            const SizedBox(height: 8),
            Chip(
              label: Text(context.tr(reward.status), style: const TextStyle(color: Colors.white, fontSize: 12)),
              backgroundColor: reward.isRedeemable ? Colors.orange : Colors.green,
            ),
            if (reward.isRedeemable) ...[
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: actioning ? null : onRedeem,
                child: Text(actioning ? context.tr('Processing…') : context.tr('Redeem to UPI (mock)')),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
