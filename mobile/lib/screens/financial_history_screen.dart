import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../features/auth/auth_controller.dart';
import '../features/rewards/models/reward_transaction.dart';
import '../features/rewards/rewards_repository.dart';
import '../features/translation/translation_text.dart';
import '../shared/state_views.dart';
import 'transaction_detail_screen.dart';

class FinancialHistoryScreen extends StatefulWidget {
  const FinancialHistoryScreen({super.key});

  @override
  State<FinancialHistoryScreen> createState() => _FinancialHistoryScreenState();
}

class _FinancialHistoryScreenState extends State<FinancialHistoryScreen> {
  final _transactions = <RewardTransaction>[];
  RewardTransactionSummary? _summary;
  bool _loading = true;
  bool _loadingMore = false;
  bool _hasMore = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load(refresh: true);
  }

  Future<void> _load({required bool refresh}) async {
    if (refresh) {
      setState(() {
        _loading = true;
        _error = null;
      });
    } else {
      if (_loadingMore || !_hasMore) return;
      setState(() => _loadingMore = true);
    }
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      final repository = context.read<RewardsRepository>();
      final results = await Future.wait([
        repository.listMyTransactions(
          accessToken: token,
          offset: refresh ? 0 : _transactions.length,
        ),
        if (refresh) repository.transactionSummary(token),
      ]);
      if (!mounted) return;
      final page = results[0] as RewardTransactionPage;
      setState(() {
        if (refresh) _transactions.clear();
        _transactions.addAll(page.transactions);
        _hasMore = page.hasMore;
        if (refresh && results.length > 1) _summary = results[1] as RewardTransactionSummary;
        _loading = false;
        _loadingMore = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
        _loadingMore = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.tr('Could not load payment history.');
        _loading = false;
        _loadingMore = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Payments & Transactions'))),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) return LoadingView(message: context.tr('Loading payment history...'));
    if (_error != null && _transactions.isEmpty) {
      return ErrorView(message: _error!, onRetry: () => _load(refresh: true));
    }
    return RefreshIndicator(
      onRefresh: () => _load(refresh: true),
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _summaryCard(),
          const SizedBox(height: 16),
          Text(context.tr('Reward transaction history'), style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_transactions.isEmpty)
            EmptyView(message: context.tr('No transactions yet.'), icon: Icons.receipt_long_outlined)
          else
            ..._transactions.map(_transactionCard),
          if (_hasMore)
            Padding(
              padding: const EdgeInsets.all(16),
              child: _loadingMore
                  ? const Center(child: CircularProgressIndicator())
                  : OutlinedButton(
                      onPressed: () => _load(refresh: false),
                      child: Text(context.tr('Load more')),
                    ),
            ),
        ],
      ),
    );
  }

  Widget _summaryCard() {
    final summary = _summary;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(context.tr('Persisted financial summary'), style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            _summaryRow(context.tr('Completed reward credits'), '₹${summary?.completedCredits ?? '0'}'),
            _summaryRow(context.tr('Completed redemptions'), '₹${summary?.completedRedemptions ?? '0'}'),
            _summaryRow(context.tr('Pending amount'), '₹${summary?.pendingAmount ?? '0'}'),
            if ((summary?.failedCount ?? 0) > 0)
              _summaryRow(context.tr('Failed records'), '${summary!.failedCount}'),
            const SizedBox(height: 8),
            Text(
              context.tr('ML price estimates are informational only and are not included in this summary.'),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }

  Widget _summaryRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _transactionCard(RewardTransaction transaction) {
    final status = transaction.status == 'SUCCEEDED'
        ? context.tr('Successful')
        : transaction.status == 'FAILED'
            ? context.tr('Failed')
            : context.tr(transaction.status);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        key: Key('financial_transaction_${transaction.txnId}'),
        leading: Icon(transaction.isCredit ? Icons.add_circle_outline : Icons.account_balance_wallet_outlined),
        title: Text(
          '${transaction.isCredit ? '+' : '-'}₹${transaction.amount}',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          '${transaction.isCredit ? context.tr('Reward credit') : context.tr('Reward redemption')}\n$status • ${transaction.createdAt}',
        ),
        isThreeLine: true,
        trailing: const Icon(Icons.chevron_right),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => TransactionDetailScreen(transaction: transaction)),
        ),
      ),
    );
  }
}
